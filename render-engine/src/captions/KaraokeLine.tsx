import {useCurrentFrame, useVideoConfig} from 'remotion';

/** 对齐置信度降级阶梯（timing.json 每段 align_confidence，取镜头组内最差）：
 *  high → 逐字高亮（对齐可信，逐字锚定可读）
 *  medium → 2~4 字词块高亮（碎片段落，块级掩盖微错位）
 *  low → 整句（对齐不可信，逐字高亮会放大错位感） */
interface Word {
  text: string;
  start_ms: number;
  end_ms: number;
  protected?: boolean;
}

interface KaraokeLineProps {
  text: string;
  words: Word[];
  offsetMs: number; // 镜头开始偏移
  confidence?: 'high' | 'medium' | 'low';
}

const HL = '#FFD54A';
const DIM = 'rgba(255,255,255,0.55)';

export function KaraokeLine({text, words, offsetMs, confidence = 'low'}: KaraokeLineProps) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const currentMs = (frame / fps) * 1000 + offsetMs;

  // 正文永远渲染 script 文本（text）；words 只提供高亮时序。
  // （修复：此前 medium/high 档直接用 words 拼正文，对齐层产出脏词（ASR 碎片如 INF/OSS）
  //  时字幕会整行显示碎片。现在脏词被跳过，且显示文本与高亮比例解耦。）
  const clean = words.filter((w) => {
    const t = (w.text || '').trim();
    if (!t) return false;
    if (!/^[\p{L}\p{N}]+$/u.test(t)) return false;          // 纯符号/标点
    if (t.length <= 3 && !/[^\x00-\x7F]/.test(t)) return false; // ≤3 位纯 ASCII 碎片
    return true;
  });
  const totalDur = clean.reduce((acc, w) => acc + Math.max(1, w.end_ms - w.start_ms), 0);
  // 当前已口语时长（当前词按比例折算）→ 高亮字符数按比例映射到 script 文本
  let spoken = 0;
  for (const w of clean) {
    const dur = Math.max(1, w.end_ms - w.start_ms);
    if (currentMs >= w.end_ms) spoken += dur;
    else if (currentMs > w.start_ms) spoken += ((currentMs - w.start_ms) / dur) * dur;
    else break;
  }
  const ratio = totalDur > 0 ? Math.min(1, spoken / totalDur) : 0;
  const charList = Array.from(text ?? '');
  const litCount = Math.round(ratio * charList.length);

  let body: React.ReactNode = text;
  if (confidence === 'high' && clean.length > 0) {
    body = charList.map((c, i) => (
      <span key={i} style={{color: i < litCount ? HL : DIM, transition: 'color 80ms'}}>
        {c}
      </span>
    ));
  } else if (confidence === 'medium' && clean.length > 0) {
    body = Array.from({length: Math.ceil(charList.length / 3)}, (_, k) => (
      <span key={k} style={{color: k * 3 < litCount ? HL : DIM, transition: 'color 120ms'}}>
        {charList.slice(k * 3, k * 3 + 3).join('')}
      </span>
    ));
  }

  const isSpeaking = clean.some((w) => currentMs >= w.start_ms && currentMs < w.end_ms);

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 60,
        left: 30,
        right: 30,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: 60,
        padding: '12px 20px',
        background: 'rgba(0,0,0,0.6)',
        borderRadius: 8,
        fontSize: 28,
        fontWeight: 500,
        color: '#fff',
        textAlign: 'center',
        lineHeight: 1.4,
        backdropFilter: 'blur(8px)',
        letterSpacing: '0.5px',
        opacity: isSpeaking ? 1 : 0.8,
        transform: isSpeaking ? 'scale(1.02)' : 'scale(1)',
        transition: 'transform 0.1s, opacity 0.2s',
      }}
    >
      {body}
    </div>
  );
}
