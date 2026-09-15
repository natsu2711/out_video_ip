/** 单镜头渲染：统一加载 job 数据，根据 recipe_ref 派发到具体组件。
 * 渲染主体在 ShotRenderer（CLI 与 Studio 预览共用）；此处仅从 --props 取数据
 * 并注入 webpack 版 CardHost / LayerCard（Studio 用 Vite 异步版）。 */
import {getInputProps} from 'remotion';
import {JobData} from '../lib/loader';
import {CardHost} from '../cards/CardHost';
import {LayerCard} from '../layers/LayerCard';
import {ShotRenderer} from './ShotRenderer';

export function ShotComposition() {
  // s5_render.py 经 --props 传入完整 JobData + shotId（组件内禁止读文件系统）
  const input = getInputProps() as unknown as (JobData & {shotId?: string}) | undefined;
  if (!input?.project || !input?.shotId) {
    throw new Error(
      'ShotComposition 需要 --props 传入完整 JobData + shotId（由 s5_render.py 组装）',
    );
  }
  const {shotId, ...data} = input;
  return (
    <ShotRenderer
      data={data}
      shotId={shotId}
      cardHost={(p) => <CardHost {...p} />}
      layerCard={LayerCard}
    />
  );
}
