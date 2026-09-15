import {Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

interface Props {
  src: string; // manifest.screenshots[shot.id]，public 相对路径
  tokens: {bg: string; anchor: string; text: string};
}

/** 真实网页截图镜头：满幅 Ken Burns 匀速缩放（线性，防 freezedetect 误判），
 * 底部渐变压暗给字幕让位。素材来自 s4_capture.py（Playwright 实拍，禁 mock）。 */
export function ScreenshotCard({src, tokens}: Props) {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const prog = Math.min(1, frame / Math.max(1, durationInFrames));
  const scale = 1.08 - 0.06 * prog; // 缓慢拉远，匀速线性

  return (
    <div style={{width: '100%', height: '100%', background: tokens.bg, overflow: 'hidden', position: 'relative'}}>
      <Img
        src={staticFile(src)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${scale})`,
          transformOrigin: '50% 40%',
        }}
      />
      {/* 底部字幕带压暗 */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: '28%',
          background: 'linear-gradient(to top, rgba(0,0,0,0.72), transparent)',
        }}
      />
    </div>
  );
}
