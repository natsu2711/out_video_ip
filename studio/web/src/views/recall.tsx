/** 召回调试：输入一句描述（RAG 检索词）+ beat 类型，看 top-N 候选卡排序
 * （WeKnora 语义命中 / 元数据打分 / 保底王三来源），点击即可预览动效并一键替换当前选中镜头的卡。 */
import React, {useCallback, useEffect, useState} from 'react';
import {Player} from '@remotion/player';
import {AbsoluteFill} from 'remotion';
import {api, type RecallCandidate, type RecallResult, type Shot} from '../api';
import {useStore} from '../store';
import {StudioCardHost, CARD_REGISTRY} from '../preview/StudioCardHost';

const BEATS = ['hook', 'point', 'step', 'case', 'contrast', 'quote', 'cta'];
const SOURCE_LABEL: Record<string, string> = {
  weknora: '语义召回', metadata: '元数据打分', fallback: '保底王',
};
const SOURCE_COLOR: Record<string, string> = {
  weknora: '#2E86AB', metadata: '#3E8989', fallback: '#999',
};

export function RecallView() {
  const s = useStore();
  const [query, setQuery] = useState('');
  const [beat, setBeat] = useState('point');
  const [topK, setTopK] = useState(8);
  const [res, setRes] = useState<RecallResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState<string | null>(null);

  const shots: Shot[] = ((s.snap?.artifacts.storyboard?.shots ?? []) as unknown as Shot[]);
  const [shotId, setShotId] = useState<string>('');
  useEffect(() => {
    if (!shotId && shots.length) setShotId(shots[0].id);
  }, [shots, shotId]);
  const shot = shots.find((x) => x.id === shotId);
  const tokens = s.projDraft?.style?.b_roll?.palette ?? {bg: '#F6F5EF', anchor: '#E4572E', text: '#1A1A1A'};

  const search = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.recall(query, beat, topK);
      setRes(r);
      setActive(r.candidates[0]?.slug ?? null);
    } finally {
      setLoading(false);
    }
  }, [query, beat, topK]);

  const applyCard = (c: RecallCandidate) => {
    if (!shot) return;
    s.updateShot(shot.id, {recipe_ref: `card:${c.slug}`} as any);
    s.notify('ok', `已换配方 card:${c.slug}（镜头 ${shot.id}），记得保存`);
  };

  const entry = active ? CARD_REGISTRY[active] : undefined;

  return (
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, padding: 16, overflow: 'auto', height: '100%'}}>
      {/* 左：查询 + 候选列表 */}
      <div style={{minWidth: 0, overflowY: 'auto'}}>
        <div className="panel" style={{padding: 12}}>
          <div style={{display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap'}}>
            <input
              style={{flex: 1, minWidth: 200}}
              placeholder="例：强调数字结论的冲击卡 / 数据增长对比"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && search()}
            />
            <select value={beat} onChange={(e) => setBeat(e.target.value)}>
              {BEATS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
            <select value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
              {[5, 8, 12, 20].map((k) => <option key={k} value={k}>top {k}</option>)}
            </select>
            <button className="primary" disabled={loading} onClick={search}>{loading ? '检索中…' : '检索'}</button>
          </div>
          {res && (
            <div style={{marginTop: 8, fontSize: 12}} className="faint">
              派生 intent：{res.intents.join(' / ')} ·
              WeKnora {res.weknora_available ? '可用' : '不可用（仅本地打分）'} ·
              命中 {res.candidates.length} 张
            </div>
          )}
        </div>

        <div style={{marginTop: 12, display: 'grid', gap: 8}}>
          {(res?.candidates ?? []).map((c, i) => (
            <div key={c.slug} className="panel"
                 onClick={() => setActive(c.slug)}
                 style={{padding: 10, cursor: 'pointer', outline: active === c.slug ? '2px solid #2E86AB' : 'none'}}>
              <div style={{display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap'}}>
                <span className="chip mono">#{i + 1}</span>
                <strong>{c.slug}</strong>
                <span className="chip" style={{color: SOURCE_COLOR[c.source]}}>{SOURCE_LABEL[c.source] ?? c.source}</span>
                {c.score > 0 && <span className="chip mono">score {c.score}</span>}
                {c.durationInFrames ? <span className="chip mono">{(c.durationInFrames / 30).toFixed(1)}s</span> : null}
              </div>
              <div className="faint" style={{fontSize: 12, marginTop: 4}}>{c.desc}</div>
              <div style={{display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap'}}>
                {Object.entries(c.arities ?? {}).map(([k, n]) => <span key={k} className="chip">{k}×{n}</span>)}
                {(c.images ?? []).map((im) => <span key={im} className="chip">{im}</span>)}
                {(c.matched_intents ?? []).map((mi) => <span key={mi} className="chip ok">{mi}</span>)}
              </div>
            </div>
          ))}
          {!res && <div className="empty" style={{padding: 20}}>输入描述后点「检索」，查看召回排序与卡槽位</div>}
        </div>
      </div>

      {/* 右：选中卡预览 + 换卡 */}
      <div style={{minWidth: 0}}>
        <div className="panel" style={{padding: 12}}>
          <div style={{display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8}}>
            <strong>{active ? `预览：${active}` : '预览'}</strong>
            <div style={{flex: 1}} />
            <select value={shotId} onChange={(e) => setShotId(e.target.value)} title="选择要替换的镜头">
              {shots.map((x) => <option key={x.id} value={x.id}>{x.id} · {(x.vo ?? '').slice(0, 14)}</option>)}
            </select>
            <button className="primary small" disabled={!active || !shot}
                    onClick={() => { const c = res!.candidates.find((x) => x.slug === active)!; applyCard(c); }}>
              替换该镜
            </button>
          </div>
          <div style={{aspectRatio: '16/9', maxHeight: 340, background: '#0A0A0A', borderRadius: 8,
                       overflow: 'hidden', margin: '0 auto'}}>
            {active && entry && (
              <Player
                key={active}
                component={React.memo(function CardProbe() {
                  return (
                    <AbsoluteFill style={{background: '#0A0A0A'}}>
                      <StudioCardHost slug={active!} shot={{vo: query || shot?.vo || '', intent: beat}} tokens={tokens} />
                    </AbsoluteFill>
                  );
                })}
                durationInFrames={Math.max(30, entry.durationInFrames ?? 90)}
                fps={30}
                compositionWidth={1920}
                compositionHeight={1080}
                loop
                autoPlay
                style={{width: '100%', height: '100%'}}
              />
            )}
          </div>
          {shot && (
            <div className="faint" style={{fontSize: 12, marginTop: 8}}>
              当前镜头 {shot.id} 配方：{shot.recipe_ref}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
