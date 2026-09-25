import { ref, onUnmounted } from 'vue'
import { api } from './api.js'

/**
 * 녹음(webm 등)을 16kHz 모노 WAV 로 바꾼다 — OpenRouter 는 webm 을 받지 않는다.
 * 브라우저가 디코딩·리샘플링까지 하므로 서버에 ffmpeg 가 필요 없다. 5초 녹음이면 약 160KB.
 */
export async function toWav16k(blob) {
  const ctx = new AudioContext()
  let decoded
  try {
    decoded = await ctx.decodeAudioData(await blob.arrayBuffer())
  } finally {
    ctx.close()
  }
  const rate = 16000
  const off = new OfflineAudioContext(1, Math.ceil(decoded.duration * rate), rate)   // 채널 1개 → 스테레오는 섞인다
  const src = off.createBufferSource()
  src.buffer = decoded
  src.connect(off.destination)
  src.start()
  const pcm = (await off.startRendering()).getChannelData(0)

  const view = new DataView(new ArrayBuffer(44 + pcm.length * 2))
  const tag = (at, s) => [...s].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)))
  tag(0, 'RIFF'); view.setUint32(4, 36 + pcm.length * 2, true); tag(8, 'WAVE')
  tag(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)   // PCM, 모노
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true)
  tag(36, 'data'); view.setUint32(40, pcm.length * 2, true)
  pcm.forEach((v, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, v)) * 0x7fff, true))
  return new Blob([view], { type: 'audio/wav' })
}

/**
 * MediaRecorder로 녹음 → 서버(Gemini)에서 한국어 텍스트로 변환.
 * 브라우저 Web Speech API(service-not-allowed) 우회.
 */
export function useSpeechRecognition(onResult) {
  const supported =
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined'

  const listening = ref(false)
  const transcribing = ref(false)
  const speechError = ref('')

  let mediaRecorder = null
  let stream = null
  let chunks = []

  function cleanupStream() {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop())
      stream = null
    }
    mediaRecorder = null
    chunks = []
  }

  function stop() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop()
    } else {
      listening.value = false
      cleanupStream()
    }
  }

  async function start() {
    if (!supported) {
      speechError.value = '이 브라우저는 마이크 녹음을 지원하지 않습니다. Chrome을 사용해 주세요.'
      return
    }

    // 이미 녹음 중이면 → 중지 후 변환
    if (listening.value) {
      stop()
      return
    }

    speechError.value = ''
    chunks = []

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      speechError.value = '마이크 권한이 거부되었습니다. 주소창 왼쪽 자물쇠 → 마이크 허용.'
      return
    }

    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : MediaRecorder.isTypeSupported('audio/mp4')
          ? 'audio/mp4'
          : ''

    try {
      mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)
    } catch {
      speechError.value = '녹음을 시작할 수 없습니다.'
      cleanupStream()
      return
    }

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data)
    }

    mediaRecorder.onstop = async () => {
      listening.value = false
      const blobType = mediaRecorder?.mimeType || mimeType || 'audio/webm'
      const blob = new Blob(chunks, { type: blobType })
      cleanupStream()

      if (blob.size < 500) {
        speechError.value = '녹음이 너무 짧습니다. 마이크를 누르고 말한 뒤 다시 눌러 주세요.'
        return
      }

      transcribing.value = true
      speechError.value = ''
      try {
        // WAV 로 못 바꾸면(오래된 브라우저) 원래 녹음을 보낸다 — 서버가 무료 Gemini 로 바로 보낸다
        const audio = await toWav16k(blob).catch(() => blob)
        const result = await api.transcribeSpeech(audio)
        if (result.ok && result.text) {
          onResult(result.text)
        } else {
          speechError.value = result.error || '음성을 인식하지 못했습니다.'
        }
      } catch (e) {
        speechError.value = e.message || '음성 변환에 실패했습니다.'
      } finally {
        transcribing.value = false
      }
    }

    mediaRecorder.start()
    listening.value = true
  }

  onUnmounted(() => {
    stop()
    cleanupStream()
  })

  return { supported, listening, transcribing, speechError, start, stop }
}
