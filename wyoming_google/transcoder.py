import asyncio
import logging
import json
import threading
import queue
#from six.moves import queue
from google.cloud import speech
#from google.cloud.speech import types


logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

IP = '0.0.0.0'
PORT = 8000

class Transcoder(object):
    """
    Converts audio chunks to text
    """
    def __init__(self, encoding, language, rate, partials):
        self.buff: queue.Queue = None
        self.encoding = encoding
        self.language = language
        self.rate = rate
        self.partials:bool = partials        
        self.closed = True
        #self.transcript = None
        self.data:bytes = None
        self.running:bool = False
        self.process_id:int = None      
        self.waiting:bool= False;  
        self.doneQueue: asyncio.Queue = asyncio.Queue()
        self.buff =  queue.Queue()

    def start(self, handler)-> None:
        """Start up streaming speech call"""
        self.data=None
        _LOGGER.debug("start called")
        while self.doneQueue.empty() is False:
            self.doneQueue.get_nowait()        
        #if self.process_id is None:
        self.process_id=threading.Thread(target=self.process, args=[handler, self.partials]).start()


    def stop(self) -> None:
        #self.doneQueue.put_nowait("finished")
        #self.closed = False
        _LOGGER.debug("transformer stop called")
    
    def restart(self, handler)->None:
        #if self.process_id is None:
        while self.doneQueue.empty() is False:
            self.doneQueue.get_nowait()        
        self.process_id=threading.Thread(target=self.process, args=[handler, self.partials]).start()        

    def response_loop(self, responses, handler, sendpartials:bool) ->None:
        final= False
        """
        Pick up the final result of Speech to text conversion
        """
        transcript:str=""
        for response in responses:
            if not response.results:
                continue
            result = response.results[0]
            if not result.alternatives:
                continue
            transcript = result.alternatives[0].transcript
            #self.transcript = transcript            
            if result.is_final:
                Final = True
            if sendpartials is True:    
                handler(transcript, result.is_final)
                transcript=""

        #if sendpartials is False:         
        if transcript != "":
            _LOGGER.debug("loop sending final result")           
            handler(transcript, True)
            #self.stop()
            #transcript=""


    def process(self, *args):
        """
        Audio stream recognition and result parsing
        """
        _LOGGER.debug("process started")
        handler = args[0]
        partials = args[1]
        _LOGGER.debug("process partials ="+str(partials))
        #You can add speech contexts for better recognition
        client = speech.SpeechClient()
        config = speech.RecognitionConfig(
            encoding=self.encoding,
            sample_rate_hertz=self.rate,
            language_code=self.language,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=partials,
            single_utterance=False)
        audio_generator = self.stream_generator()
        requests = (speech.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)
        _LOGGER.debug("processing for partial results")
        responses = client.streaming_recognize(streaming_config, requests)
        try:
            self.response_loop(responses, handler,  self.partials)
        except:
            self.start(handler)
            _LOGGER.debug("transcoder restarted")
        _LOGGER.debug("transcoder ended")    

    def process1(self, *args):
        """
        Audio stream recognition and result parsing
        """
        #You can add speech contexts for better recognition
        #cap_speech_context = types.SpeechContext(phrases=["Add your phrases here"])
        client = speech.SpeechClient()
        config = speech.RecognitionConfig(
            encoding=self.encoding,
            sample_rate_hertz=self.rate,
            language_code=self.language
            #speech_contexts=[cap_speech_context,],
            #model='command_and_search'
        )
        _LOGGER.debug("process started")
        handler=args[0]
        partials=args[1]
        _LOGGER.debug("send partial results="+str(partials))
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=partials,
            single_utterance=False)

        while True:
            _LOGGER.debug("getting queued content via generator")
            audio_generator = self.stream_generator()
            requests = (speech.StreamingRecognizeRequest(audio_content=content)
                        for content in audio_generator)
            _LOGGER.debug("processing requests")
            responses = client.streaming_recognize(streaming_config, requests)
            try:
                self.response_loop(responses, handler, self.partials)
            except:
                self.process_id = None                 
                self.restart(handler)     
                _LOGGER.debug("process break") # 
                break;
        #self.restart(handler)
        #self.closed= False
        _LOGGER.debug("process end")

    def stream_generator(self):
        while self.closed == True:
            _LOGGER.debug("generator start")
            chunk = self.buff.get()
            if chunk is None:
                return
            data = [chunk]
            while True:
                try:
                    chunk = self.buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
            yield b''.join(data)


    def stream_generator1(self):
         while self.closed == True:
            #_LOGGER.debug("clearing data")
            #data = None             
            # get a block of data, 
            try:
                chunk = self.buff.get(block=True)
            except queue.Empty:    
                _LOGGER.debug("whoops, data queue empty")
                return
            # if the buffer for transcription is empty
            if self.data is None: 
                # set it
                self.data = [chunk]
                _LOGGER.debug("data size=%d",len(self.data))
            else:
                # append more
                self.data.append(chunk)   
            # loop til the queue is empty     
            while self.doneQueue.empty() is True:
                _LOGGER.debug("reading more buffer")
                try:
                    # get a chunk if any
                    chunk = self.buff.get(block=False)   
                    # if none, we are done
                    if chunk is None:
                        if self.data is None:
                            return
                        else:
                            _LOGGER.debug("ending read buffer loop, to return data")
                            break
                    # else append
                    self.data.append(chunk)
                except queue.Empty:
                    _LOGGER.debug("no additional data")
                    if self.data is not None:
                        _LOGGER.debug("was some data")
                        break
            #_LOGGER.debug("returning data")                        
            yield b''.join(self.data)    
            #data = None      

    def write(self, data) -> None:
        """
        Writes data to the buffer
        """        
        self.buff.put(data)
        _LOGGER.debug("data added to buffer")


"""
async def audio_processor(websocket, path):
    '''
    Collects audio from the stream, writes it to buffer and return the output of Google speech to text
    '''

    transcoder = Transcoder(
        encoding=config["format"],
        rate=config["rate"],
        language=config["language"]
    )
    transcoder.start(handler)

    transcoder.write(data)
"""
