import wave
import asyncio

from timeit import default_timer as timer
from datetime import timedelta

import argparse
import logging

from wyoming.asr import Transcript, Transcribe
from wyoming.audio import AudioChunk, AudioStart, AudioStop, AudioChunkConverter
from wyoming.client import AsyncTcpClient
from wyoming.info import Describe
from wyoming.event import async_write_event, async_read_event

_LOGGER = logging.getLogger("wav2text_client")

# expected Audio recording parameters
RATE = 16000

# used in the read function to get a chunk of the audio file
CHUNK_SIZE = int(RATE / 10)  # 100ms

# connect to the server asr port and return the connection object
#@staticmethod
async def connect(uri:str) -> AsyncTcpClient:
    tcp = AsyncTcpClient.from_uri(uri)
    await tcp.connect()
    return tcp

# need to be async to use await on wyoming event functions
async def main() -> None:
    """Transcribe speech from audio file."""
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code: str = "en-US"  # a BCP-47 language tag
    InterimResults: bool = False
    debug:bool  = False    
    
    # define the arguments and --help
    parser = argparse.ArgumentParser()
    parser.add_argument("server", help="uri of the server to connect to")
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to transcribe")
    parser.add_argument("--language", help="Google language", default="en-US")
    parser.add_argument("--partial", action="store_true",default=False, help="send partial responses, False/True,  default False")
    parser.add_argument("--debug", action="store_true", default=False, help="Log DEBUG messages")
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    args = parser.parse_args()

    # do the debugging logging
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if args.debug:
        debug = args.debug

    if args.language:
        #if debug == True:
        _LOGGER.debug("language parm="+args.language)
        language_code= args.language.strip()

    # if there should be paretial results
    if args.partial:
       InterimResults: bool =args.partial

    if debug == True:
       _LOGGER.debug("server uri="+args.server)  
       
    # loop thru the wav files (may be one, space separated)
    for wave_file in args.wav_file:
        if debug:
            _LOGGER.debug("wave file="+wave_file)               
        asr_server_connection=None
        try:
 	    # connect to the asr server
            asr_server_connection=await connect(args.server)               
        except:
            print("unable to connect to asr at "+args.server)
            return
        # use each wav file in turn
        input_wav_file =  wave.open(wave_file, "r")
        if debug:
            transcribe_start = timer()
            
        with input_wav_file:

            # send the describe event
            await asr_server_connection.write_event( Describe().event())
            # read the info response
            info_event=await asr_server_connection.read_event()

            # send the transcribe event with language
            await asr_server_connection.write_event(Transcribe( language=language_code).event())
            # no response from Transcribe

            # Input from wave file the audio characteristics, may need to convert to  asr expected format
            rate = input_wav_file.getframerate()
            width = input_wav_file.getsampwidth()
            channels = input_wav_file.getnchannels()

            if debug:
                _LOGGER.debug("file rate="+str(rate)+" width="+str(width)+" channels="+str(channels))

            # get audio data from the file,      
            audio_bytes = input_wav_file.readframes(CHUNK_SIZE)
            
            # create a converter to insure the audio data is in the right format for the ASR
            converter = AudioChunkConverter(
                rate=RATE, width=2, channels=1
            )
            
            # loop thru the audio buffer, 
            while audio_bytes:
                # convert to asr format as required (converter output format set before)
                chunk = converter.convert(
                    AudioChunk(rate, width, channels, audio_bytes)
                )

                # send this chunk to the asr 
                await asr_server_connection.write_event(chunk.event())
                # get more data from the wav file
                audio_bytes = input_wav_file.readframes(CHUNK_SIZE)
                
                # if interim results (partials to be accumulated)
                if InterimResults :
                    transcript=await asr_server_connection.read_event()
                    if debug: 
                        _LOGGER.debug("returned text="+transcript.data["text"])
                    if audio_bytes==None:
                        break;
            
            # no more data, tell asr we are finished sending chunks
            # we will expect a full text output now
            await asr_server_connection.write_event(AudioStop().event())
            transcript=await asr_server_connection.read_event()
            if debug:
                end = timer()
                _LOGGER.debug("elapsed="+str(timedelta(seconds=end-transcribe_start))+" asr returned text="+transcript.data["text"])
            else:
                print(transcript.data["text"])

        # done with this asr 
        await asr_server_connection.disconnect();

if __name__ == "__main__":
  # because we want to use await in the main function we need 
  # to launch as async task 
  asyncio.run(main())
