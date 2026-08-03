// Landmarks file format (matches worker write_landmarks_npz):
//   line 1: JSON header {"shape": [T, 478, 3], "dtype": "float32", "schema": "mediapipe-v1", "fps": 30.0, "meta_shape": [T, 4]}
//   then: T*478*3 float32 = landmarks_3d
//   then: T*4 float32 = [ts_ms, conf, yaw, pitch]

export interface LoadedLandmarks {
  points: Float32Array[]; // per-frame: 478 * 3 floats
  confidences: Float32Array;
  fps: number;
  schema: string;
  timestamps: Float32Array;
  yaw: Float32Array;
  pitch: Float32Array;
}

export async function fetchLandmarks(url: string): Promise<LoadedLandmarks> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load landmarks: ${res.status}`);
  let buf = new Uint8Array(await res.arrayBuffer());
  if (buf[0] === 0x1f && buf[1] === 0x8b) {
    const compressed = new Blob([buf.slice().buffer]).stream();
    const decompressed = compressed.pipeThrough(new DecompressionStream('gzip'));
    buf = new Uint8Array(await new Response(decompressed).arrayBuffer());
  }
  // Find first newline
  let nl = 0;
  for (; nl < buf.length; nl++) {
    if (buf[nl] === 0x0a) break;
  }
  const header = JSON.parse(new TextDecoder().decode(buf.subarray(0, nl)));
  const [T, N, C] = header.shape as [number, number, number];
  const pointsCount = T * N * C * 4; // float32 bytes
  const pointsBuf = buf.slice(nl + 1, nl + 1 + pointsCount);
  // JSON header length is not guaranteed to be 4-byte aligned. `slice`
  // creates an aligned buffer and avoids RangeError in Float32Array.
  const pointsFlat = new Float32Array(pointsBuf.buffer);
  // Split per frame
  const stride = N * C;
  const points: Float32Array[] = new Array(T);
  for (let i = 0; i < T; i++) {
    points[i] = pointsFlat.subarray(i * stride, (i + 1) * stride);
  }
  const metaCount = (header.meta_shape?.[0] ?? T) * (header.meta_shape?.[1] ?? 4) * 4;
  const metaBuf = buf.slice(nl + 1 + pointsCount, nl + 1 + pointsCount + metaCount);
  const meta = new Float32Array(metaBuf.buffer);
  const metaStride = (header.meta_shape?.[1] ?? 4) as number;
  const timestamps = new Float32Array(T);
  const confidences = new Float32Array(T);
  const yaw = new Float32Array(T);
  const pitch = new Float32Array(T);
  for (let i = 0; i < T; i++) {
    timestamps[i] = meta[i * metaStride];
    confidences[i] = meta[i * metaStride + 1];
    yaw[i] = meta[i * metaStride + 2];
    pitch[i] = meta[i * metaStride + 3];
  }
  return {
    points,
    confidences,
    fps: header.fps ?? 30.0,
    schema: header.schema ?? 'unknown',
    timestamps,
    yaw,
    pitch,
  };
}
