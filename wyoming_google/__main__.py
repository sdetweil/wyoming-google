#!/usr/bin/env python3
import argparse
import asyncio
import logging
import os
from functools import partial

from wyoming.info import  AsrModel, AsrProgram, Attribution, Info
from wyoming.server import AsyncServer

from  .const import CREDENTIALS_FILE,  GOOGLE_LANGUAGES
from .handler import GoogleEventHandler

_LOGGER = logging.getLogger(__name__)

async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True, help="unix:// or tcp://")
    parser.add_argument(
        "--language",
        help="Default language to set for transcription",
    )
    parser.add_argument("--config", required=True, help="config folder name") 
    parser.add_argument("--intermediate_results", action="store_true",  help="if you want results on the fly") 
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    _LOGGER.debug(args)

    if args.language == "auto":
        # google does not understand "auto"
        args.language = "en"

    if os.path.isfile(args.config+CREDENTIALS_FILE) == False:
        raise FileNotFoundError
    
    #set the authentication info for google speech api used in handler

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = args.config+CREDENTIALS_FILE

    wyoming_info = Info(
        asr=[
            AsrProgram(
                name="google-streaming",
                description="google cloud streaming asr",
                attribution=Attribution(
                    name="Sam Detweiler",
                    url="https://github.com/sdetweil/google-streaming-asr",
                ),
                installed=True,
                models=[
                    AsrModel(
                        name="google-streaming",
                        description="google cloud streaming asr",
                        attribution=Attribution(
                            name="rhasspy",
                            url="https://github.com/rhasspy/models/",
                        ),
                        installed=True,
                        languages=GOOGLE_LANGUAGES,
                    )
                ]                
            )
        ]
    )

    server = AsyncServer.from_uri(args.uri)
    _LOGGER.debug(wyoming_info)
    model_lock = asyncio.Lock()
    await server.run(        
        partial(
            GoogleEventHandler,
            wyoming_info,
            args,
            0,
            model_lock
        )
    )
    _LOGGER("exiting")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
