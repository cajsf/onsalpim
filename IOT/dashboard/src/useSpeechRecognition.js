import { ref, onUnmounted } from 'vue'
import { api } from './api.js'

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
        const result = await api.transcribeSpeech(blob)
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
