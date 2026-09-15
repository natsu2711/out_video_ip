import {Composition} from 'remotion';
import {ShotComposition} from './ShotComposition';
import {CardSnapshot} from '../cards/CardSnapshot';
import type {JobData} from '../lib/loader';

export const RemotionVideo: React.FC = () => {
  return (
    <>
    <Composition
      id="Shot"
      component={ShotComposition as any}
      // 默认值会被 calculateMetadata 按 props 覆盖（时长/fps/画幅随镜头与 project.json 变化）
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1920}
      calculateMetadata={({props}) => {
        const data = props as unknown as JobData & {shotId: string};
        const shot = data.storyboard.shots.find((s) => s.id === data.shotId);
        const fps = data.project.canvas.fps;
        // 与 s5_render.py 的 int() 截断保持一致（floor）
        const durationInFrames = shot
          ? Math.max(
              1,
              Math.floor(
                ((shot.time.end_ms - shot.time.start_ms) / 1000) * fps,
              ),
            )
          : 300;
        return {
          durationInFrames,
          fps,
          width: data.project.canvas.width,
          height: data.project.canvas.height,
        };
      }}
    />
    <Composition
      id="CardSnapshot"
      component={CardSnapshot as any}
      durationInFrames={40}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{slug: 'number-counter'}}
    />
    </>
  );
};
