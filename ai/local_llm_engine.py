"""
Cybzenor - Yerel Küçük Dil Modeli Motoru (Local LLM Engine)
Herhangi bir bulut API anahtarı gerektirmeyen, tamamen offline çalışan küçük bir
dil modeliyle (GGUF, llama.cpp üzerinden) OSINT metni anlama ve kelime çağrışımı
üretme yeteneği sağlar. Model indirilmemiş veya kütüphane kurulu değilse sessizce
devre dışı kalır; çağıran taraf (LocalAIProvider) bu durumda statik kural motoruna düşer.
"""

import json
import re
from pathlib import Path
from typing import Any, Optional

from config.settings import BASE_DIR
from utils.logger import logger

# Varsayılan model: Qwen2.5-1.5B-Instruct (Q4_K_M, ~1GB), çok dilli (Türkçe dahil) bir
# model. 0.5B varyantı denendi ama yapılandırılmış Türkçe metin anlama görevlerinde
# (OSINT çıkarımı, kategori/çağrışım üretimi) talimatları güvenilir takip edemedi;
# 1.5B belirgin şekilde daha tutarlı JSON çıktısı üretiyor. models/ dizinine indirilir.
DEFAULT_REPO_ID = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
DEFAULT_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODELS_DIR = BASE_DIR / "models"


def _parse_json_leniently(text: str) -> Any:
    """
    Küçük yerel modelin yanıtından JSON çıkarır. Model iki tür hata yapabiliyor:
    (1) İstenen düz JSON dizisi yerine onu bir nesnenin içine sarmak
        (örn. {"bilinen": ["a", "b"]} yerine ["a", "b"] istenmişti), veya
    (2) Sözdizimi hatalı, kusurlu JSON üretmek (kaçak virgül/parantez gibi).
    Önce standart (sıkı) ayrıştırma denenir; başarısız olursa metindeki İLK köşeli
    parantez bloğunu ([...], nesnenin içinde iç içe olsa bile) bulup onu ayrıştırmayı
    dener; o da bozuksa son çare olarak bloktaki tüm tırnaklı string'leri (madde
    listesi öğeleri) regex ile tek tek çıkarır. Hiçbiri işe yaramazsa ValueError fırlatır.
    """
    # 1. Sıkı deneme: metindeki ilk [...] veya {...} bloğunu olduğu gibi ayrıştır.
    match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
    if not match:
        raise ValueError(f"Yerel model yanıtında JSON bulunamadı: {text[:200]}")
    block = match.group(1)
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        pass

    # 2. Model, istenen diziyi bir nesnenin içine sarmış olabilir — nesnenin İÇİNDEKİ
    #    ilk [...] dizisini ayrıca dener (örn. {"bilinen": [...]} -> [...]).
    inner_match = re.search(r'\[.*\]', block, re.DOTALL)
    if inner_match:
        try:
            return json.loads(inner_match.group(0))
        except json.JSONDecodeError:
            # 3. Son çare: dizi bloğu sözdizimsel olarak bozuk (kaçak virgül/parantez
            #    gibi) ama içindeki tırnaklı string öğeleri hâlâ okunabilir durumda.
            items = re.findall(r'"([^"]{1,80})"', inner_match.group(0))
            if items:
                return items

    raise ValueError(f"Yerel model geçerli/ayrıştırılabilir bir JSON döndürmedi: {text[:200]}")


class LocalLLMEngine:
    """llama.cpp üzerinden yerel bir GGUF modelini yükleyip JSON tabanlı tamamlamalar üretir."""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self.model_path = model_path or (MODELS_DIR / DEFAULT_FILENAME)
        self._llm = None
        self._load_attempted = False
        self._load_failed = False

    def is_model_present(self) -> bool:
        return self.model_path.is_file()

    def is_available(self) -> bool:
        """Kütüphane kurulu mu ve model dosyası diskte mevcut mu?"""
        if not self.is_model_present():
            return False
        try:
            import llama_cpp  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_loaded(self) -> bool:
        """Modeli tembel (lazy) olarak yükler. Başarısızsa bir daha denemez."""
        if self._llm is not None:
            return True
        if self._load_attempted and self._load_failed:
            return False
        self._load_attempted = True

        if not self.is_available():
            self._load_failed = True
            return False

        try:
            from llama_cpp import Llama
            logger.info(f"Yerel dil modeli yükleniyor: {self.model_path.name} (ilk çağrıda biraz sürebilir)...")
            self._llm = Llama(
                model_path=str(self.model_path),
                n_ctx=2048,
                n_threads=None,
                verbose=False,
            )
            logger.info("Yerel dil modeli başarıyla yüklendi.")
            return True
        except Exception as e:
            logger.warning(f"Yerel dil modeli yüklenemedi: {e}")
            self._load_failed = True
            return False

    def generate_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 700, temperature: float = 0.4) -> Any:
        """
        Modelden bir tamamlama alır ve içindeki ilk JSON yapısını (liste veya nesne) döndürür.
        Model JSON etrafına ekstra metin eklerse bile regex ile JSON bloğu çıkarılır.

        temperature: Olgusal/çıkarım görevleri (metinden bilgi çekme) için düşük (örn. 0.1-0.2)
        verilmeli — yüksek sıcaklık, küçük modelin metinde HİÇ geçmeyen bilgi uydurmasını
        (halüsinasyon) ve aynı girdiye her seferinde farklı yanıt vermesini kolaylaştırır.
        Öneri/çağrışım üretimi gibi göreceli olarak "yaratıcı" görevlerde varsayılan kalabilir.
        """
        if not self._ensure_loaded():
            raise RuntimeError("Yerel dil modeli kullanılabilir değil.")

        response = self._llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = response["choices"][0]["message"]["content"]
        return _parse_json_leniently(text)


def download_model(repo_id: str = DEFAULT_REPO_ID, filename: str = DEFAULT_FILENAME) -> Path:
    """
    Modeli Hugging Face Hub'dan models/ dizinine indirir. huggingface_hub kurulu olmalıdır.
    Zaten indirilmişse tekrar indirmez.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = MODELS_DIR / filename
    if target_path.is_file():
        logger.info(f"Model zaten mevcut: {target_path}")
        return target_path

    from huggingface_hub import hf_hub_download
    logger.info(f"Model indiriliyor: {repo_id}/{filename} -> {MODELS_DIR} (boyuta göre birkaç dakika sürebilir)...")
    downloaded_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(MODELS_DIR),
    )
    logger.info(f"Model indirme tamamlandı: {downloaded_path}")
    return Path(downloaded_path)


# Global singleton örneği (LocalAIProvider tarafından paylaşılır, her çağrıda yeniden yüklenmez)
local_llm_engine = LocalLLMEngine()
