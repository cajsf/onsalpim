"""stt_eval.py — 받아쓰기 비교: Gemini(제품과 같은 호출) 대 Whisper large-v3-turbo(로컬, faster-whisper).

    pip install faster-whisper                  # 이 측정에만 필요하다 (제품 requirements 에는 넣지 않는다)
    pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"   # NVIDIA GPU 로 돌릴 때 (없으면 CPU 로 돈다)
    python stt_eval.py 녹음폴더                   # Gemini + Whisper
    python stt_eval.py 녹음폴더 --only whisper     # Whisper 만 (API 비용 0)
Whisper 모델은 처음 돌릴 때 받는다 (large-v3-turbo 약 1.6GB, 사용자 폴더 .cache/huggingface).
9/25 이 노트북 CPU(i7-1165G7, int8)로는 5초 녹음 하나에 약 9초 — 시연 PC 가 CPU 뿐이면 쓰기 어렵다.

녹음폴더:
    3_민성.m4a        '문장번호_아무거나.확장자'. 휴대폰 녹음(m4a·mp3·wav·webm 등)을 그대로 둔다
    sentences.txt    (없어도 된다) 한 줄에 한 문장, 줄 번호 = 문장 번호. 없으면 같은 폴더의 stt_sentences.txt(24문장)
결과: 녹음폴더/stt_eval.csv (녹음마다 한 줄) + 화면에 요약.

녹음은 팀원 목소리다 — 저장소 안에 두지 말 것. 두 쪽 모두 제품과 같은 16kHz 모노 WAV 를 받는다.
Gemini 기본은 OpenRouter(data_collection=deny — 입력을 수집하지 않는 공급자로만). 무료 Gemini 로 재려면
--gemini gemini-3.1-flash-lite (무료 등급은 입력을 Google 제품 개선에 쓰고 사람이 볼 수 있다).

채점은 AI 없이 코드로 한다:
    글자 오류율(CER) — 띄어쓰기·문장부호를 빼고 비교
    숫자  — sentence_facts.numbers 가 정답과 같은가 (6시간·30도 …)
    호수  — sentence_facts.named_homes: 맞음 / 빠짐(눈에 보이게 틀림) / 다른 호수(조용히 틀림 — 가장 위험)
    지연  — 녹음 하나 받아쓰는 시간 (모델을 올리는 시간은 뺀다)
"""
import argparse
import csv
import io
import os
import re
import sys
import time
import wave

import sentence_facts as facts

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".webm", ".flac", ".3gp", ".amr"}
# Whisper 에 주는 앞 문맥 — 숫자를 아라비아 숫자로 쓰게 유도한다. 실제 호수(101·102·201·202)는 넣지 않는다:
# Gemini 에서 예시 호수에 답이 끌려가는 것을 봤다 (speech_transcribe.PROMPT 주석)
WHISPER_HINT = "305호 무활동 기준을 7시간 40분으로 바꾸고, 25도가 넘으면 알려줘."


def _norm(s):
    return re.sub(r"[\s.,!?~'\"“”‘’·…]", "", (s or "").replace("%", "퍼센트"))   # '20%' 와 '20퍼센트' 는 같게


def cer(ref, hyp):
    """글자 오류율 — 편집 거리 / 정답 글자 수. 띄어쓰기·문장부호는 뺀다."""
    r, h = _norm(ref), _norm(hyp)
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i]
        for j, hc in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return prev[-1] / max(len(r), 1)


def home_check(ref, hyp):
    """'맞음' | '빠짐'(정답 호수가 안 나옴) | '다른 호수'(정답에 없는 호수가 나옴) | ''(둘 다 호수 없음)"""
    want, got = facts.named_homes(ref), facts.named_homes(hyp)
    if not want and not got:
        return ""
    if want == got:
        return "맞음"
    return "다른 호수" if set(got) - set(want) else "빠짐"


assert cer("102호만 6시간으로", "102호만 6 시간으로.") == 0
assert cer("20퍼센트 아래로", "20% 아래로") == 0
assert abs(cer("102호", "배기호") - 3 / 4) < 1e-9
assert home_check("102호 기준 30분 줄여줘", "배기호 기준 30분 줄여줘") == "빠짐"
assert home_check("102호 기준 30분 줄여줘", "101호 기준 30분 줄여줘") == "다른 호수"
assert home_check("전체 세대", "전체 세대") == ""


def _wav_bytes(pcm):
    """float32 16kHz 모노 → WAV 바이트 (대시보드가 서버에 보내는 것과 같은 형식)"""
    import numpy as np
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def load_clips(folder):
    """[(파일, 문장번호, 말한 사람, 정답 문장)]"""
    path = os.path.join(folder, "sentences.txt")
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stt_sentences.txt")
    print(f"문장 목록: {path}")
    with open(path, encoding="utf-8-sig") as f:
        sentences = [line.strip() for line in f]
    clips = []
    for name in sorted(os.listdir(folder)):
        stem, ext = os.path.splitext(name)
        m = re.match(r"(\d+)[_\- ]?(.*)$", stem)
        if ext.lower() not in AUDIO_EXT or not m:
            continue
        no = int(m.group(1))
        if not 1 <= no <= len(sentences) or not sentences[no - 1]:
            print(f"  건너뜀: {name} — sentences.txt 에 {no}번 문장이 없다")
            continue
        clips.append((name, no, m.group(2), sentences[no - 1]))
    return clips


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--only", choices=["gemini", "whisper"])
    ap.add_argument("--gemini", default="openrouter:google/gemini-3.1-flash-lite",
                    help="speech_transcribe 모델 이름 (기본: 제품 1순위와 같은 OpenRouter 유료 경로)")
    ap.add_argument("--whisper", default="large-v3-turbo")
    ap.add_argument("--device", help="cuda 또는 cpu (없으면 GPU 가 있으면 cuda)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    from faster_whisper import WhisperModel, decode_audio   # 오디오 읽기(PyAV)에도 쓴다 — ffmpeg 설치가 필요 없다
    clips = load_clips(args.folder)
    if not clips:
        print("녹음이 없다 — '문장번호_이름.확장자' 파일과 sentences.txt 를 확인할 것")
        return
    print(f"녹음 {len(clips)}개 · 문장 {len({c[1] for c in clips})}개 · 말한 사람 {len({c[2] for c in clips})}명")
    audio = {name: decode_audio(os.path.join(args.folder, name), sampling_rate=16000) for name, *_ in clips}

    systems = {}
    if args.only != "whisper":
        import speech_transcribe
        systems["gemini"] = lambda pcm: speech_transcribe.transcribe(_wav_bytes(pcm), "a.wav", "audio/wav",
                                                                     models=[args.gemini])
    if args.only != "gemini":
        # Windows 에서 pip 로 받은 CUDA 라이브러리(nvidia-*-cu12)는 파이썬이 저절로 찾지 못한다 — 폴더를 알려 준다
        import site
        for sp in site.getsitepackages():
            for lib in ("cublas", "cudnn"):
                d = os.path.join(sp, "nvidia", lib, "bin")
                if os.name == "nt" and os.path.isdir(d):
                    os.add_dll_directory(d)
                    os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
        import ctranslate2
        device = args.device or ("cuda" if ctranslate2.get_cuda_device_count() else "cpu")
        if device == "cpu" and not args.device:
            print("  GPU 를 못 찾아 CPU 로 돈다 (느리다). NVIDIA GPU PC 라면 위 docstring 의 nvidia-* 패키지를 설치할 것")
        t = time.time()
        model = WhisperModel(args.whisper, device=device, compute_type="float16" if device == "cuda" else "int8")
        print(f"Whisper {args.whisper} ({device}) 올리는 데 {time.time() - t:.1f}초")

        def whisper(pcm, hint=None):
            segs, _ = model.transcribe(pcm, language="ko", beam_size=5, initial_prompt=hint,
                                       condition_on_previous_text=False)
            return {"ok": True, "text": "".join(s.text for s in segs).strip(), "error": ""}
        whisper(next(iter(audio.values())))   # 첫 호출은 초기화가 섞여 느리다 — 지연에서 뺀다
        systems["whisper"] = whisper
        systems["whisper+힌트"] = lambda pcm: whisper(pcm, WHISPER_HINT)

    rows = []
    for name, no, who, ref in clips:
        for sys_name, fn in systems.items():
            t = time.time()
            out = fn(audio[name])
            sec = time.time() - t
            hyp = out["text"]
            rows.append({"파일": name, "문장": no, "말한 사람": who, "방식": sys_name, "정답": ref, "받아쓴 것": hyp,
                         "CER": round(cer(ref, hyp), 3) if out["ok"] else "",
                         "숫자": ("맞음" if facts.numbers(hyp) == facts.numbers(ref) else "틀림") if facts.numbers(ref) else "",
                         "호수": home_check(ref, hyp) if out["ok"] else "",
                         "지연(초)": round(sec, 2), "오류": out["error"]})
            r = rows[-1]
            if not out["ok"] or r["CER"] or r["숫자"] == "틀림" or r["호수"] not in ("", "맞음"):
                print(f"  {name} [{sys_name}] {hyp or out['error'][:80]}  (CER {r['CER']}, 숫자 {r['숫자'] or '-'}, 호수 {r['호수'] or '-'})")

    path = os.path.join(args.folder, "stt_eval.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"\n{'방식':<12}{'평균 CER':>9}{'문장 그대로':>11}{'숫자 맞음':>10}{'호수 맞음·빠짐·다른 호수':>24}{'평균·최대 지연':>16}{'오류':>5}")
    for sys_name in systems:
        rs = [r for r in rows if r["방식"] == sys_name]
        ok = [r for r in rs if not r["오류"]]
        num = [r for r in ok if r["숫자"]]
        home = [r["호수"] for r in ok]
        lat = [r["지연(초)"] for r in rs]
        print(f"{sys_name:<12}{sum(r['CER'] for r in ok) / max(len(ok), 1):>9.3f}"
              f"{sum(r['CER'] == 0 for r in ok):>7}/{len(rs)}"
              f"{sum(r['숫자'] == '맞음' for r in num):>7}/{len(num)}"
              f"{home.count('맞음'):>14} · {home.count('빠짐')} · {home.count('다른 호수')}"
              f"{sum(lat) / len(lat):>10.2f} · {max(lat):.2f}초{len(rs) - len(ok):>5}")
    print(f"\n녹음마다: {path}")


if __name__ == "__main__":
    main()
