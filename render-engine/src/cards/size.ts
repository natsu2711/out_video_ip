/** 卡设计尺寸契约（唯一权威）：
 * talkcraft 移植卡 = 960×540；shotcraft（sc-）卡 = 1920×1080。
 * 卡组件永远输出设计尺寸原稿；任何缩放由宿主容器按 designSizeOf 计算，全链路只缩一次。 */
export function designSizeOf(slug: string): {w: number; h: number} {
  return slug.startsWith('sc-') ? {w: 1920, h: 1080} : {w: 960, h: 540};
}
