/** 全局视觉 token——吸收来源：
 *  - 字号/字重阶梯：guizang-ppt 瑞士风（"越大越细，越小越粗"，中文标题分档，最小字号下限）
 *  - 色板轮换：vox-director（bold flat color per beat，每拍换色反单调）
 * 用法：镜头组件字号一律从 TYPE 取，禁止随手写 px；B-roll 底色按镜头序号从 BEAT_COLORS 轮换。 */

export const TYPE = {
  display: 150, // 数字 hero / 超大标题
  h1: 96,       // 镜头主标题
  h2: 64,       // 副标题 / 金句
  h3: 44,       // 区块标题
  body: 32,     // 正文
  caption: 24,  // 标签 / 注释
  note: 20,     // 最小下限（手机可读底线，不得再小）
} as const;

/** "越大越细，越小越粗"（guizang 瑞士阶梯核心规则） */
export const weightFor = (size: number): number => (size >= 96 ? 500 : size >= 64 ? 700 : 900);

/** 大字收紧（瑞士排版）：letter-spacing -.04em / line-height .95 */
export const TIGHT = { letterSpacing: '-0.04em', lineHeight: 0.95 } as const;

/** vox 式每拍色板（bold flat colors）：B-roll 镜头底色按 shotIdx % N 轮换 */
export const BEAT_COLORS = ['#E4572E', '#2E86AB', '#F3A712', '#3E8989', '#B33F62'];
