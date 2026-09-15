/** 呈现层（presentation grammar）：内容「怎么出现」的正交轴。
 * 与主体（A/B-roll）、氛围（C-roll overlay）完全解耦——任意主体 × 任意呈现自由组合。
 * 借鉴：talkcraft 三段式（入场 0.2~0.8s 用力 > 出场）+ shotcraft 镜头卡运动语法。
 * 全部确定性（帧驱动），每镜至多一种呈现（lint 守门）。 */
import React from 'react';
import {useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';

export type PresentationKind = 'wipe_mask' | 'rise_fade' | 'slam_in' | 'blur_focus' | 'none';

/** 依次层现（stagger reveal）：列表型主体的逐条入场由各配方内部实现（StepsCard/ListGrid
 * 自带 stagger）；本组件负责「整块内容」的入场语法。 */

export function Presentation({kind, children, delayFrames = 6}: {
  kind?: PresentationKind;
  children: React.ReactNode;
  delayFrames?: number;
}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const f = Math.max(0, frame - delayFrames);

  if (!kind || kind === 'none') {
    return <>{children}</>;
  }

  // 三段式口径：入场 0.2~0.8s，入场永远比出场用力（这里只管入场，长驻交给全局相机+叠层）
  if (kind === 'wipe_mask') {
    // 蒙版擦除：内容被块「刷」出来（clip-path 右→0），talkcraft 命门口径：字/块同步刷出
    const p = interpolate(f, [0, fps * 0.55], [0, 1], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });
    const ease = 1 - Math.pow(1 - p, 4); // power3.out
    return (
      <div style={{width: '100%', height: '100%', clipPath: `inset(0 ${(1 - ease) * 100}% 0 0)`}}>{children}</div>
    );
  }

  if (kind === 'rise_fade') {
    // 上升浮现：translateY 40→0 + opacity
    const p = interpolate(f, [0, fps * 0.6], [0, 1], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });
    const ease = 1 - Math.pow(1 - p, 3);
    return (
      <div style={{width: '100%', height: '100%', opacity: ease, transform: `translateY(${(1 - ease) * 42}px)`}}>{children}</div>
    );
  }

  if (kind === 'slam_in') {
    // 砸入：scale 1.16→1 带回弹（spring 过冲）+ 快速实化
    const pop = spring({frame: f, fps, config: {damping: 11, stiffness: 130, mass: 0.9}});
    const opacity = interpolate(f, [0, fps * 0.18], [0, 1], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });
    return (
      <div style={{
        width: '100%', height: '100%',
        opacity,
        transform: `scale(${1.16 - 0.16 * Math.max(0, Math.min(1, pop))})`,
      }}>{children}</div>
    );
  }

  // blur_focus：虚实聚焦 blur 14→0（电影感开场）。
  // 完成后不得残留任何 filter/transform —— 常驻 blur(0px) 在无头渲染下会与子树
  // mixBlendMode(multiply) 冲突导致整镜黑屏（实测踩坑：paolu 19 镜全黑）
  const p = interpolate(f, [0, fps * 0.7], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const ease = 1 - Math.pow(1 - p, 3);
  if (ease >= 1) {
    return <>{children}</>;
  }
  return (
    <div style={{
      opacity: ease,
      filter: `blur(${(1 - ease) * 14}px)`,
      transform: `scale(${0.96 + 0.04 * ease})`,
    }}>{children}</div>
  );
}
