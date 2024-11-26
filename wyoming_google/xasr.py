from wyoming.asr import Transcript
from dataclasses import dataclass
from typing import Any, Dict, Optional
from wyoming.event import Event, Eventable

DOMAIN = "asr"
_TRANSCRIPT_TYPE = "xtranscript"

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
        return event_type ==  _TRANSCRIPT_TYPE    
 
    def event(self) -> Event:
        data: Dict[str, Any] = {"text": self.text}
        if self.language is not None:
            data["language"] = self.language
        data["is_final"]=self.is_final

        return Event(type=_TRANSCRIPT_TYPE, data=data)    

    @staticmethod
    def from_event(event: Event) -> "xTranscript":
        assert event.data is not None
        return xTranscript(text=event.data["text"], language=event.data.get("language"), is_final=event.data.get("is_final"))