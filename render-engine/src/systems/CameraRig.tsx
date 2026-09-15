import {useCurrentFrame, useVideoConfig} from 'remotion';

interface CameraRigProps {
  motion?: {type: string; amount: number; anchor?: string} | null;
  children: React.ReactNode;
}

export function CameraRig({motion, children}: CameraRigProps) {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const progress = frame / durationInFrames;

  let style: React.CSSProperties = {};
  if (motion?.type === 'pulse') {
    // 重音脉冲：在中间位置放大
    const mid = durationInFrames / 2;
    const dist = Math.abs(frame - mid);
    const scaleVal = dist < 10 ? 1 + 0.08 * (1 - dist / 10) : 1;
    style.transform = `scale(${scaleVal})`;
  } else if (motion?.type === 'scale-in') {
    const val = Math.min(1, progress * 1.5);
    style.transform = `scale(${val})`;
  }

  return <div style={{width: '100%', height: '100%', ...style}}>{children}</div>;
}

/** 呼吸微动：元素缓慢呼吸变化 */
export function useIdle() {
  const frame = useCurrentFrame();
  const val = Math.sin(frame * 0.02) * 0.5 + 100; // 99.5% ~ 100.5%
  return {scale: val / 100};
}