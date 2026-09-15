/** CLI 渲染端的图层卡槽（webpack require.context 加载卡组件，仅 Remotion bundler 使用）。
 * Studio（Vite）经 ShotRenderer 的 layerCard 注入自己的异步实现，不 import 本文件。 */
import {CARD_REGISTRY, loadCardComponent, setCardContent, type CardEntry} from '../cards/index';
import {buildCardContent} from '../cards/content';

export function LayerCard({slug, config, tokens}: {slug: string; config: any; tokens: any}) {
  const entry: CardEntry | undefined = CARD_REGISTRY[slug];
  if (entry) {
    setCardContent(buildCardContent(entry, {vo: '', intent: '', config}));
  }
  const Card = entry ? loadCardComponent(slug) : null;
  if (!Card || !entry) {
    return (
      <div style={{width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                   color: '#900', fontSize: 22, background: '#fff'}}>图层卡未移植: {slug}</div>
    );
  }
  // 设计尺寸契约：输出原稿，缩放由 LayerHost 计算
  return <Card />;
}
