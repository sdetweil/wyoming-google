from wyoming.asr import Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
# from wyoming.error import Error
from wyoming.event import Event, async_write_event

class google_model:

    async def transcribe(server: str, port:int, wav_file:str, language:str ) ->bool:

        asr_server= AsyncTcpClient(server, port)



        return False
