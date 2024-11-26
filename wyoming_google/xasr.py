from wyoming.asr import Transcript, Transcribe
from dataclasses import dataclass
from typing import Any, Dict, Optional
from wyoming.event import Event, Eventable

DOMAIN = "asr"
_xTRANSCRIPT_TYPE = "xtranscript"
_xTRANSCRIBE_TYPE = "xtranscribe"

@dataclass
class xTranscript(Transcript):

    name: Optional[str] = None
    """Name of ASR model to use"""

    language: Optional[str] = None
    """Language of spoken audio to follow"""

    context: Optional[Dict[str, Any]] = None
    """Context from previous interactions."""    

    is_final: Optional[bool] = False

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type ==  _xTRANSCRIPT_TYPE    
 
    def event(self) -> Event:
        data: Dict[str, Any] = {"text": self.text}
        if self.language is not None:
            data["language"] = self.language
        data["is_final"]=self.is_final

        return Event(type=_xTRANSCRIPT_TYPE, data=data)    

    @staticmethod
    def from_event(event: Event) -> "xTranscript":
        assert event.data is not None
        return xTranscript(text=event.data["text"], language=event.data.get("language"), is_final=event.data.get("is_final"))
    
@dataclass    
class xTranscribe(Transcribe):
    """Transcription request to ASR system.

    Followed by AudioStart, AudioChunk+, AudioStop
    """

    name: Optional[str] = None
    """Name of ASR model to use"""

    language: Optional[str] = None
    """Language of spoken audio to follow"""

    context: Optional[Dict[str, Any]] = None
    """Context from previous interactions."""

    sendPartials: Optional[bool] = False;
    """indicate if the receiver should send partial results if possible"""

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _xTRANSCRIBE_TYPE

    def event(self) -> Event:
        data: Dict[str, Any] = {}
        if self.name is not None:
            data["name"] = self.name

        if self.language is not None:
            data["language"] = self.language
        data["sendPartials"] = self.sendPartials  

        return Event(type=_xTRANSCRIBE_TYPE, data=data)

    @staticmethod
    def from_event(event: Event) -> "xTranscribe":
        data = event.data or {}
        return xTranscribe(name=data.get("name"), language=data.get("language"), sendPartials=data.get("sendPartials"))