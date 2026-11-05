"""Voice registry metadata for the Kokoro v1.0 voice pack (54 voices).

Prefix encodes language + gender: a=American, b=British, e=Spanish, f=French,
h=Hindi, i=Italian, p=Portuguese, z=Mandarin, j=Japanese; f/m = female/male.
zh/ja voices need dedicated G2P pipelines this runtime does not ship, so they
are hidden from the picker by default.
"""
from __future__ import annotations

# style notes only where documented on the model card; others are unmarked
_NOTES = {
    "af_heart": "warm, default pick",
    "af_bella": "soft, expressive",
    "af_nicole": "soft, aspirated",
    "af_aoede": "soft, breathy",
    "af_kore": "stern",
    "af_sarah": "soft",
    "af_nova": "shy",
    "af_sky": "soft, upbeat",
    "am_adam": "neutral",
    "am_michael": "neutral, clear",
    "am_puck": "playful",
    "am_santa": "seasonal, jolly",
    "bf_emma": "neutral, British",
    "bf_isabella": "neutral, British",
    "ef_dora": "Spanish, neutral",
    "em_alex": "Spanish, male",
    "ff_siwis": "French, neutral",
    "hf_alpha": "Hindi",
    "hf_beta": "Hindi",
    "if_sara": "Italian",
    "im_nicola": "Italian, male",
    "pf_dora": "Portuguese (BR)",
    "pm_alex": "Portuguese (BR), male",
}

_PREFIX_LANG = {
    "af": ("en-us", "US"),
    "am": ("en-us", "US"),
    "bf": ("en-gb", "UK"),
    "bm": ("en-gb", "UK"),
    "ef": ("es", "ES"),
    "em": ("es", "ES"),
    "ff": ("fr-fr", "FR"),
    "hf": ("hi", "HI"),
    "hm": ("hi", "HI"),
    "if": ("it", "IT"),
    "im": ("it", "IT"),
    "pf": ("pt-br", "PT"),
    "pm": ("pt-br", "PT"),
}

ALL_V1_0_VOICES = [
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore",
    "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael",
    "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "ef_dora", "em_alex", "em_santa",
    "ff_siwis",
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola",
    "pf_dora", "pm_alex", "pm_santa",
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
    "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
]


def voice_info(name: str) -> dict:
    """Return metadata for a voice name; unknown names get a minimal entry."""
    prefix = name[:2]
    lang, region = _PREFIX_LANG.get(prefix, (None, None))
    gender = "female" if prefix[1] == "f" else "male"
    return {
        "name": name,
        "lang": lang,                    # None => needs zh/ja pipeline, unsupported
        "region": region,
        "gender": gender,
        "note": _NOTES.get(name, ""),
        "supported": lang is not None,
    }


def catalog() -> list[dict]:
    return [voice_info(v) for v in ALL_V1_0_VOICES]


def default_lang_for(name: str) -> str:
    info = voice_info(name)
    return info["lang"] or "en-us"
