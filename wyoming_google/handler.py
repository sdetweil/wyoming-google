"""Event handler for clients of the server."""
import argparse
import asyncio
import logging
import re
import sys
from queue import Queue
from threading import Thread

from google.cloud import speech
from wyoming.asr import Transcribe
from .xasr import xTranscript
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
        self.interimResults =  self.cli_args.intermediate_results
        # setup for speech reco
        self.speechclient:object=None
        self.speechconfig:object= None
        self.streaming_config:object = None
        self.text:str = None
        self.audio_converter = AudioChunkConverter(
            rate=self.rate,
            width=2,
            channels=1,
        )
        #self.request=None
        self.debug: bool = self.cli_args.debug
        self.language = self.cli_args.language
        self.audio=bytes()
        self.responseQueue = Queue()
        _thread = Thread(target=self.sendResponses)
        _thread.start()
    
    @staticmethod
    def listen_print_loop(responses: object, partial: bool, debug: bool) -> str:
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
            for response in responses:
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
                        sys.stdout.write(transcript + overwrite_chars + "\r")
                        sys.stdout.flush()

                        num_chars_printed = len(transcript)
                        if debug == True:
                            print("not final")

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
        _LOGGER.debug("event type='"+event.type+"'\n")

        if AudioChunk.is_type(event.type):
            if self.speechclient == None:
                await self.handle_event(Transcribe().event())
            _LOGGER.debug("received AudioChunk event request")
            chunk = AudioChunk.from_event(event)
            _LOGGER.debug("chunk info rate="+str(chunk.rate)+" width="+str(chunk.width)+" channels="+str(chunk.channels))
            _LOGGER.debug("expected info rate="+str(self.rate)+" width=2 channels=1")
            chunk = self.audio_converter.convert(chunk)
            _LOGGER.debug("chunk audio length="+str(len(chunk.audio)))

            self.audio += chunk.audio 

            _LOGGER.debug("audio length="+str(len(self.audio)))
            if self.interimResults == True:
                #if len(self.audio) > self.rate:
                requests = [speech.StreamingRecognizeRequest(audio_content=self.audio)]
                # add this content onto the last
                responses = self.speechclient.streaming_recognize(
                    self.streaming_config, requests
                )
            
                # Now, put the transcription responses to use.
                self.text=self.listen_print_loop(responses, self.interimResults, self.debug)       
                if len(self.text) >0:
                    self.saveOnQueue(xTranscript(text=''.join(self.text),is_final=False).event())
                #if len(self.text) >0:
                #    self.text=''
                #    self.audio=bytes()
                    #await self.write_event(Transcript(text=self.text).event())     
            _LOGGER.debug("Completed AudioChunk request\n")
            return True
        
        elif AudioStop.is_type(event.type):
            _LOGGER.debug("received AudioStop event request")
            if self.speechclient==None:
                _LOGGER.debug("speech vars=null=True")
                #self.speechclient=speech.SpeechClient()
            else:
                _LOGGER.debug("speech vars=null=False")

            _LOGGER.debug("audio length="+str(len(self.audio)))
            #if len(self.audio) > self.rate:
            requests = [speech.StreamingRecognizeRequest(audio_content=self.audio)]
            # add this content onto the last
            responses = self.speechclient.streaming_recognize(
                self.streaming_config, requests
            )
        
            # Now, put the transcription responses to use.
            self.text=self.listen_print_loop(responses, self.interimResults, self.debug)      

            _LOGGER.debug("recognized text="+self.text)
            self.saveOnQueue(xTranscript(text=''.join(self.text),is_final=True).event())
            #await self.write_event(Transcript(text=self.text).event())
            _LOGGER.debug("Completed AudioStop request\n")

            return True        

        elif Transcribe.is_type(event.type):
            _LOGGER.debug("received Transcribe event request")
            transcribe = Transcribe.from_event(event)
            _LOGGER.debug("received transcribe from event successful")
            if transcribe.language:
                self.language = transcribe.language
                _LOGGER.debug("Language set to %s", transcribe.language)
            self.text=''                
            #setup to transcribe
            self.speechclient = speech.SpeechClient()
            self.speechconfig = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.rate,
                language_code=self.language,
            )

            self.streaming_config = speech.StreamingRecognitionConfig(
                config=self.speechconfig, interim_results=self.interimResults
            )
            speech.StreamingRecognizeRequest(streaming_config=self.streaming_config)
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
