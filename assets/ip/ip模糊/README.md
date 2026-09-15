# IP 形象（短发 T 恤女孩）素材约定

把你的 IP 图放进本目录，管线自动消费（s4_manifest 扫描 → manifest.ip_poses）：

```
assets/ip/
├── ref/          # 任意参考图（立绘/三视图/表情包，不进状态机，仅生图参考）
├── idle.png      # 姿态切图（可选）：待机
├── point.png     # 指/讲解
├── confident.png # 自信
└── shock.png     # 惊讶
```

- 文件名 = 姿态名（idle/point/confident/shock/question），png/jpg/webp 均可
- 只放 ref/ 也能跑：A-roll 自动降级为单图 flip-book 模式；姿态齐全后自动升级为
  剪纸角色状态机（ARollScene 按镜头序轮换姿态 + 呼吸微动）
- 白底图会以 multiply 混合融进纸底舞台；透明 PNG 效果最佳
