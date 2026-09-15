# 集成验证清单

## 高优先级（2/2）

### 1. 主题色预设系统

- [x] `schemas/project.schema.json` - 新增 `theme` 字段（enum 10 套）
- [x] `pipeline/theme_tokens.py` - 主题色定义 + `get_theme()` 工具
- [x] `scripts/apply_theme.py` - 自动应用工具
- [x] `scripts/s0_init.py` - 默认 `theme: "ink-classic"`
- [ ] **待测**: 新建 job 后运行 `apply_theme.py` 验证 palette 更新

```bash
# 测试命令
python scripts/s0_init.py jobs test-job "Test"
python scripts/apply_theme.py jobs/test-job
cat jobs/test-job/project.json | grep -A 5 "palette"
```

### 2. 校验脚本扩展（Playwright）

- [x] `scripts/s6_qa_playwright.py` - 9 条规则桩实现
- [x] `scripts/s6_qa.py` - 集成 playwright 检测
- [x] Playwright 安装：`.venv/bin/pip install playwright`
- [x] Chromium 安装：`.venv/bin/playwright install chromium`
- [ ] **待测**: 运行完整 S6 阶段验证 `qa/playwright-report.json` 生成

```bash
# 测试命令（需要有成片）
python scripts/s6_qa.py jobs/2026-0902-fake-effort
ls jobs/2026-0902-fake-effort/qa/playwright-report.json
```

---

## 中优先级（2/2）

### 3. 版式骨架组件（6 个）

| 组件 | 文件 | 注册 | [ ] 待测 |
|---|---|---|---|
| ImageLedCover | `src/shots/ImageLedCover.tsx` | ✅ | 预览渲染 |
| PipelineSteps | `src/shots/PipelineSteps.tsx` | ✅ | 预览渲染 |
| CompareCardEnhanced | `src/shots/CompareCardEnhanced.tsx` | ✅ | 预览渲染 |
| KPI_Tower | `src/shots/KPI_Tower.tsx` | ✅ | 预览渲染 |
| MatrixHero | `src/shots/MatrixHero.tsx` | ✅ | 预览渲染 |
| MapCard | `src/shots/MapCard.tsx` | ✅ | 预览渲染 |

- [x] 所有组件已注册到 `ShotComposition.SHOT_COMPONENTS`
- [x] 所有组件 import 已添加
- [x] 测试 storyboard: `jobs/2026-0902-fake-effort/storyboard-new-components.json`
- [ ] **待测**: Remotion 预览模式验证 6 个组件渲染

```bash
# 测试命令
cd render-engine
npm run preview
# 在浏览器中逐一预览 S001-S006
```

### 4. 截图美化工具

- [x] `scripts/enhance_screenshot.py` - 10 套风格支持
- [x] guizang WebP 背景路径引用：`/Users/bainazi/Documents/outtt/2other_pic/guizang-social-card-skill/`
- [x] Help 输出验证通过
- [ ] **待测**: 实际截图美化输出验证

```bash
# 测试命令
cp assets/ip-placeholder/ip-three-view_00001_.png /tmp/test-input.png
python scripts/enhance_screenshot.py /tmp/test-input.png /tmp/test-output.png --style ikb
ls -lh /tmp/test-output.png
```

---

## 未采纳功能（确认排除）

- [x] 三闸门审批协议 - 已回滚 `pipeline/state.py`
- [x] 双色 Ink 系统 - 未集成
- [x] 认知锚点可视化 - 未集成
- [x] 19 种手绘风格 - 未集成

---

## 外部技能路径引用验证

| 技能 | 路径 | [ ] 验证 |
|---|---|---|
| guizang-social-card-skill | `/Users/bainazi/Documents/outtt/2other_pic/guizang-social-card-skill/` | 目录存在 |
| mono-color-skill | `/Users/bainazi/Documents/outtt/2other_pic/mono-color-skill/` | 目录存在 |
| ian-xiaohei-illustrations | `/Users/bainazi/Documents/outtt/2other_pic/ian-xiaohei-illustrations/` | 目录存在 |
| Punk-Skill | `/Users/bainazi/Documents/outtt/2other_pic/Punk-Skill/` | 目录存在 |
| gbro-collage-broll | `/Users/bainazi/Documents/outtt/1other_video/gbro-collage-broll/` | 目录存在 |
| hand-drawn-styles | `/Users/bainazi/Documents/outtt/1other_video/hand-drawn-styles/` | 目录存在 |

```bash
# 验证命令
ls -d /Users/bainazi/Documents/outtt/2other_pic/guizang-social-card-skill/
ls -d /Users/bainazi/Documents/outtt/1other_video/gbro-collage-broll/
```

---

## 下一步建议

1. 运行主题色应用测试
2. 启动 Remotion 预览验证 6 个新版式组件
3. 截图美化实际测试
4. 完整 S6 阶段 Playwright QA 测试（需成片）

---

**集成完成时间**: 2026-09-02
**新增文件**: 11 个
**新增组件**: 6 个