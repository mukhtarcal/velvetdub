/** Length of a video file, if the browser can read it (not every format plays in a browser).
 * Resolves to null instead of failing: the runtime is only a nicety on the page. */
export function readRuntime(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const video = document.createElement('video')
    const url = URL.createObjectURL(file)
    const finish = (seconds: number | null) => {
      window.clearTimeout(timer)
      video.removeAttribute('src')
      URL.revokeObjectURL(url)
      resolve(seconds)
    }
    const timer = window.setTimeout(() => finish(null), 4000)
    video.preload = 'metadata'
    video.onloadedmetadata = () => finish(Number.isFinite(video.duration) ? video.duration : null)
    video.onerror = () => finish(null)
    video.src = url
  })
}
