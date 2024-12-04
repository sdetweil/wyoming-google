"""Event handler for clients of the server."""
import argparse
import asyncio
import logging
import re
import sys
from queue import Queue
from threading import Thread
from .transcoder import Transcoder

from google.cloud import speech
#from wyoming.asr import Transcribe
from .xasr import xTranscript, xTranscribe
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStop
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler

_LOGGER = logging.getLogger(__name__)


class GoogleEventHandler(AsyncEventHandler):
    """Event handler for clients."""

    def __init__(
        self,
        wyoming_info: Info,
        cli_args: argparse.Namespace,
        model: 0,
        model_lock: asyncio.Lock,        
        *args,
        **kwargs,
    ) -> None:

        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.google_info_event = wyoming_info.event()
        self.rate = 16000
        self.interimResults =  self.cli_args.intermediate_results == True
        self.sendPartials: bool = False
        self.text:str = None
        self.transcoder : Transcoder = None
        self.audio_converter = AudioChunkConverter(
            rate=self.rate,
            width=2,
            channels=1,
        )
        self.final:bool = False
        #self.request=None
        self.debug: bool = self.cli_args.debug
        self.language = self.cli_args.language
        self.audio=bytes()
        self.responseQueue = Queue()
        self.connected= False
        _thread = Thread(target=self.sendResponses)
        _thread.start()
        self._is_final_sent:bool = False

        _LOGGER.debug("interimResults="+str(self.interimResults))
            
    def transcript_handler(self, text:str, final:bool)-> None:
        _LOGGER.debug("send transcript, text='%s' final=%r", text, final)  
        self.text=text                  
        self.saveOnQueue(xTranscript(text=''.join(self.text),is_final=final).event())

    def listen_print_loop(self, responses: object, partial: bool, debug: bool) -> str:
        """Iterates through server responses and prints them.

        The responses passed is a generator that will block until a response
        is provided by the server.

        Each response may contain multiple results, and each result may contain
        multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
        print only the transcription for the top alternative of the top result.

        In this case, responses are provided for interim results as well. If the
        response is an interim one, print a line feed at the end of it, to allow
        the next result to overwrite it, until the response is a final one. For the
        final one, print a newline to preserve the finalized transcription.

        Args:
            responses: List of server responses
            partial   : whether partial results should be returned
            debug    : whether debug messages should be produced

        Returns:
            The transcribed text.
        """
        num_chars_printed = 0
        transcript = ""
        if responses != None:
             count = 50
             for response in responses:
                if --count >0:
                    if not response.results:
                        if debug == True:
                            print("no results")
                        continue

                    # The `results` list is consecutive. For streaming, we only care about
                    # the first result being considered, since once it's `is_final`, it
                    # moves on to considering the next utterance.
                    result = response.results[0]
                    if not result.alternatives:
                        if debug == True:
                            print("no alternatives")
                        continue

                    # Display the transcription of the top alternative.
                    transcript = result.alternatives[0].transcript
                    # print("transcript2=",transcript)

                    # Display interim results, but with a carriage return at the end of the
                    # line, so subsequent lines will overwrite them.
                    #
                    # If the previous result was longer than this one, we need to print
                    # some extra spaces to overwrite the previous result
                    overwrite_chars = " " * (num_chars_printed - len(transcript))

                    if not result.is_final:
                        if partial == True:
                            if debug == True:
                                sys.stdout.write(transcript + overwrite_chars + "\r")
                                sys.stdout.flush()

                            num_chars_printed = len(transcript)
                            if debug == True:
                                print("not final")
                            self.final= False    

                    else:
                        print(transcript.strip() + overwrite_chars)
                        if debug == True:
                            print("is final")
                        # Exit recognition if any of the transcribed phrases could be
                        # one of our keywords.
                        # print("transcript=",transcript)
                        if re.search(r"\b(exit|quit)\b", transcript, re.I):
                            if debug == True:
                                print("Exiting..")
                            break
                        self.final= True
                        num_chars_printed = 0

        return transcript  
    
    def sendResponses(self) -> None:
        _LOGGER.debug("sendResponses ready")
        while True:
            responseEvent = self.responseQueue.get(block=True)
            _LOGGER.debug("pulled event from queue")
            asyncio.run(self.write_event(responseEvent))
            _LOGGER.debug("sent event from queue\n")

    def saveOnQueue(self, event:Event) ->None:        
        # make sure to clone the text as it might change in the next AudioChunk event\
        _LOGGER.debug("saving event on queue")
        self.responseQueue.put_nowait(event)            

    async def handle_event(self, event: Event) -> bool:

        #_LOGGER.debug("event type='"+event.type+"'\n")

        if AudioChunk.is_type(event.type):
            if self.connected is False:
                _LOGGER.debug("not connected")
                return True
            if self._is_final_sent == True:
                return True
            _LOGGER.debug("received AudioChunk event request")
            chunk = AudioChunk.from_event(event)
            _LOGGER.debug("chunk info rate="+str(chunk.rate)+" width="+str(chunk.width)+" channels="+str(chunk.channels))
            _LOGGER.debug("expected info rate="+str(self.rate)+" width=2 channels=1")
            chunk = self.audio_converter.convert(chunk)

            _LOGGER.debug("audio length=%d",len(chunk.audio))
            if self.interimResults == True and self.sendPartials == True:
                _LOGGER.debug("sending chunk to transcoder")
                self.transcoder.write(chunk.audio)
                _LOGGER.debug("Completed AudioChunk request buffer size= %d \n", len(chunk.audio))
            else:
                _LOGGER.debug("appending data size=%d", len(chunk.audio))
                self.audio+=chunk.audio
                _LOGGER.debug("appended  data size=%d", len(self.audio))
                _LOGGER.debug("Completed AudioChunk request buffer size= %d \n", len(self.audio))

           
            return True
        
        elif AudioStop.is_type(event.type):
            _LOGGER.debug("received AudioStop event request")

            #if self.interimResults == False or self.sendPartials == False:
            if len(self.audio) >0:
                _LOGGER.debug("sending all data to transcoder, len=%d", len(self.audio))
                self.transcoder.write(self.audio)
                _LOGGER.debug("audio stop, check for transformer running")
            if len(self.text) >0:
                self.saveOnQueue(xTranscript(text=''.join(self.text), is_final=True).event())

            _LOGGER.debug("Completed AudioStop request\n")
            self.transcoder.stop()       
            self.connected = False     
            return True        

        elif xTranscribe.is_type(event.type):
            if self.connected == False:
                self.connected = True
                #_LOGGER.debug("received Transcribe event request")
                transcribe = xTranscribe.from_event(event)
                _LOGGER.debug("received transcribe from event successful")
                if transcribe.language:
                    self.language = transcribe.language
                    _LOGGER.debug("Language set to %s", transcribe.language)
                if self.interimResults is True and transcribe.sendPartials == True:                
                    self.sendPartials = True
                else:    
                    self.sendPartials = False
                self._is_final_sent = False;        
                self.data=None        
                self.text=''    
                self.audio = bytes()    
                self.final= False          

                if self.transcoder is None:   
                    _LOGGER.debug("starting transcoder")       
                    self.transcoder = Transcoder(
                        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                        language=self.language,
                        rate=self.rate,                
                        partials=self.sendPartials
                    )
                    self.transcoder.start(self.transcript_handler)                    
                else:
                    _LOGGER.debug("transcoder already running")
                    self.transcoder.restart(self.transcript_handler); 

                _LOGGER.debug("Completed Transcribe request\n")
            return True
        elif xTranscript.is_type(event.type):
            _LOGGER.debug("Transcript received")
            #self.saveOnQueue(text=self.text)
            self.saveOnQueue(xTranscript(text=''.join(self.text), is_final=True).event())
            #await self.write_event(Transcript(text=self.text).event())
            _LOGGER.debug("Completed Transcript request\n")
            return False        
        
        elif Describe.is_type(event.type):
            _LOGGER.debug("received Describe event request")
            self.saveOnQueue(self.google_info_event)
            #await self.write_event(self.google_info_event)
            _LOGGER.debug("Sent Describe info\n")
            return True                    
        
        _LOGGER.debug("unknown event="+event.type)

        return True
    async def disconnect(self)->None:
        self.connected=False
        _LOGGER.debug("client disconnected")