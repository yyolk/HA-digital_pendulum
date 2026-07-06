import logging
import voluptuous as vol
from .player_base import BasePlayer

_LOGGER = logging.getLogger(__name__)

TTS_LOCALE_MAP = {
    "en": "en-US",
    "it": "it-IT",
    "de": "de-DE",
    "fr": "fr-FR",
    "es": "es-ES",
    "pt": "pt-PT",
    "pl": "pl-PL",
    "cs": "cs-CZ",
    "sk": "sk-SK",
}


def _to_tts_locale(language: str) -> str:
    if not language:
        return "en-US"
    if "-" in language:
        return language
    return TTS_LOCALE_MAP.get(language.lower(), "en-US")


class GooglePlayer(BasePlayer):

    async def play_default_chime(self):
        pass

    async def play_chime(self, chime_url: str):
        base_data = {
            "entity_id": self.player,
            "media_content_id": chime_url,
            "media_content_type": "audio/mp3",
        }
        try:
            # Alcuni media_player (es. Google Cast/Sonos) supportano "announce"
            # per non interrompere la riproduzione in corso. Non tutte le
            # integrazioni (es. Apple TV/HomePod) lo accettano: in quel caso
            # voluptuous solleva MultipleInvalid e ripieghiamo senza il flag.
            await self.hass.services.async_call(
                "media_player",
                "play_media",
                {**base_data, "announce": True},
                blocking=True,
            )
        except vol.Invalid:
            _LOGGER.debug(
                "Digital Pendulum: 'announce' non supportato da '%s', ritento senza",
                self.player,
            )
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "play_media",
                    base_data,
                    blocking=True,
                )
            except Exception:
                await self.play_default_chime()
        except Exception:
            await self.play_default_chime()

    def _find_tts_entity(self) -> str | None:
        preferred = [
            "tts.home_assistant_cloud",
            "tts.google_translate_en_com",
            "tts.google_translate",
        ]
        for entity_id in preferred:
            if self.hass.states.get(entity_id) is not None:
                return entity_id
        for state in self.hass.states.async_all("tts"):
            return state.entity_id
        return None

    async def speak(self, text: str, language: str = "en"):
        """Annuncio vocale nella lingua specificata."""
        tts_entity = self._find_tts_entity()
        if tts_entity:
            base_data = {
                "entity_id": tts_entity,
                "media_player_entity_id": self.player,
                "message": text,
                "language": _to_tts_locale(language),
            }
            try:
                # blocking=True è necessario perché il fallback/except
                # abbia senso: con blocking=False l'errore emerge nel
                # core di HA dopo che questo except è già terminato.
                await self.hass.services.async_call(
                    "tts",
                    "speak",
                    base_data,
                    blocking=True,
                )
            except Exception as e:
                _LOGGER.error(
                    "Digital Pendulum: errore TTS su '%s' con entity '%s': %s",
                    self.player,
                    tts_entity,
                    e,
                )
        else:
            await self.hass.services.async_call(
                "tts",
                "google_translate_say",
                {
                    "entity_id": self.player,
                    "message": text,
                    "language": _to_tts_locale(language),
                },
                blocking=False,
            )
