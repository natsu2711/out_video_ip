# 主题色预设（来自 guizang-social-card-skill）
# Editorial 6 套
INK_CLASSIC = {
    "name": "墨水经典 Ink Classic",
    "bg": "#0a0a0b",
    "text": "#f1efea",
    "anchor": "#f1efea",
    "description": "通用默认、商业话题、不知道选啥时最稳"
}

INDIGO_PORCELAIN = {
    "name": "靛蓝瓷 Indigo Porcelain",
    "bg": "#0a1f3d",
    "text": "#f1f3f5",
    "anchor": "#f1f3f5",
    "description": "科技、研究、AI、技术分享"
}

FOREST_INK = {
    "name": "森林墨 Forest Ink",
    "bg": "#1a2e1f",
    "text": "#f5f1e8",
    "anchor": "#f5f1e8",
    "description": "自然、可持续、户外、非虚构"
}

KRAFT_PAPER = {
    "name": "牛皮纸 Kraft Paper",
    "bg": "#2a1e13",
    "text": "#eedfc7",
    "anchor": "#eedfc7",
    "description": "怀旧、人文、阅读、文学"
}

DUNE = {
    "name": "沙丘 Dune",
    "bg": "#1f1a14",
    "text": "#f0e6d2",
    "anchor": "#f0e6d2",
    "description": "艺术、设计、创意、时尚"
}

MIDNIGHT_INK = {
    "name": "午夜墨 Midnight Ink",
    "bg": "#0e0d0c",
    "text": "#ece2cf",
    "anchor": "#d4a04a",
    "description": "游戏 key art / 夜景 / 影调封面 / 深色题材"
}

# Swiss 4 套
IKB = {
    "name": "克莱因蓝 IKB",
    "bg": "#0A0A0A",
    "text": "#FFFFFF",
    "anchor": "#002FA7",
    "description": "通用默认、商业发布、AI 产品、方法论"
}

LEMON = {
    "name": "柠檬黄 Lemon",
    "bg": "#0A0A0A",
    "text": "#FFFFFF",
    "anchor": "#FFD500",
    "description": "年轻、运动、零售、消费品、Y2K"
}

LEMON_GREEN = {
    "name": "柠檬绿 Lemon Green",
    "bg": "#0A0A0A",
    "text": "#FFFFFF",
    "anchor": "#C5E803",
    "description": "生态、健康、Z 世代、绿色品牌"
}

SAFETY_ORANGE = {
    "name": "安全橙 Safety Orange",
    "bg": "#0A0A0A",
    "text": "#FFFFFF",
    "anchor": "#FF6B35",
    "description": "警示、新闻、工业、活力主题"
}

# 主题映射表
THEME_MAP = {
    "ink-classic": INK_CLASSIC,
    "indigo-porcelain": INDIGO_PORCELAIN,
    "forest-ink": FOREST_INK,
    "kraft-paper": KRAFT_PAPER,
    "dune": DUNE,
    "midnight-ink": MIDNIGHT_INK,
    "ikb": IKB,
    "lemon": LEMON,
    "lemon-green": LEMON_GREEN,
    "safety-orange": SAFETY_ORANGE,
}

def get_theme(theme_id: str) -> dict:
    """获取主题色配置，若不存在返回默认 IKB"""
    return THEME_MAP.get(theme_id, IKB)
# ---- html-ppt-skill 36 主题吸收（2026-09-09，一次性生成）----

ACADEMICPAPER = {
    "name": "paper — 学术论文 (academic-paper)",
    "bg": "#fdfcf8",
    "text": "#0a0a0a",
    "anchor": "#1a3a7a",
    "description": "html-ppt-skill academic-paper（浅色）",
}


ARCTICCOOL = {
    "name": "cool — 冷色调 蓝/青/石板灰 (arctic-cool)",
    "bg": "#f2f6fb",
    "text": "#0e1f33",
    "anchor": "#1e6fb0",
    "description": "html-ppt-skill arctic-cool（浅色）",
}


AURORA = {
    "name": "极光渐变 (aurora)",
    "bg": "#06091c",
    "text": "#e8f0ff",
    "anchor": "#5ef2c6",
    "description": "html-ppt-skill aurora（深色）",
}


BAUHAUS = {
    "name": "几何+原色 (bauhaus)",
    "bg": "#f4efe3",
    "text": "#111111",
    "anchor": "#e03c27",
    "description": "html-ppt-skill bauhaus（浅色）",
}


BLUEPRINT = {
    "name": "蓝图工程 (blueprint)",
    "bg": "#0b3a6f",
    "text": "#e8f3ff",
    "anchor": "#ffffff",
    "description": "html-ppt-skill blueprint（深色）",
}


CATPPUCCINLATTE = {
    "name": "latte — catppuccin 浅 (catppuccin-latte)",
    "bg": "#eff1f5",
    "text": "#4c4f69",
    "anchor": "#8839ef",
    "description": "html-ppt-skill catppuccin-latte（浅色）",
}


CATPPUCCINMOCHA = {
    "name": "mocha — catppuccin 深 (catppuccin-mocha)",
    "bg": "#1e1e2e",
    "text": "#cdd6f4",
    "anchor": "#cba6f7",
    "description": "html-ppt-skill catppuccin-mocha（深色）",
}


CORPORATECLEAN = {
    "name": "clean — 企业商务 (corporate-clean)",
    "bg": "#ffffff",
    "text": "#0a2540",
    "anchor": "#0a2540",
    "description": "html-ppt-skill corporate-clean（浅色）",
}


CYBERPUNKNEON = {
    "name": "neon — 赛博朋克霓虹 (cyberpunk-neon)",
    "bg": "#000000",
    "text": "#f5f7ff",
    "anchor": "#ff2bd6",
    "description": "html-ppt-skill cyberpunk-neon（深色）",
}


DRACULA = {
    "name": "dracula 深色 (dracula)",
    "bg": "#282a36",
    "text": "#f8f8f2",
    "anchor": "#bd93f9",
    "description": "html-ppt-skill dracula（深色）",
}


EDITORIALSERIF = {
    "name": "serif — 杂志风衬线，高级 (editorial-serif)",
    "bg": "#faf7f2",
    "text": "#1b1410",
    "anchor": "#8a2a1c",
    "description": "html-ppt-skill editorial-serif（浅色）",
}


ENGINEERINGWHITEPRINT = {
    "name": "whiteprint — 工程白图 (engineering-whiteprint)",
    "bg": "#ffffff",
    "text": "#0a1e46",
    "anchor": "#0a1e46",
    "description": "html-ppt-skill engineering-whiteprint（浅色）",
}


GLASSMORPHISM = {
    "name": "毛玻璃 (glassmorphism)",
    "bg": "#0b1024",
    "text": "#f2f4ff",
    "anchor": "#7dd3fc",
    "description": "html-ppt-skill glassmorphism（深色）",
}


GRUVBOXDARK = {
    "name": "dark (gruvbox-dark)",
    "bg": "#282828",
    "text": "#ebdbb2",
    "anchor": "#fabd2f",
    "description": "html-ppt-skill gruvbox-dark（深色）",
}


JAPANESEMINIMAL = {
    "name": "minimal — 和风极简 (japanese-minimal)",
    "bg": "#fafaf5",
    "text": "#1a1a18",
    "anchor": "#d93a2a",
    "description": "html-ppt-skill japanese-minimal（浅色）",
}


MAGAZINEBOLD = {
    "name": "bold — 杂志大标题 (magazine-bold)",
    "bg": "#f5efe2",
    "text": "#0a0a0a",
    "anchor": "#ea5a1a",
    "description": "html-ppt-skill magazine-bold（浅色）",
}


MEMPHISPOP = {
    "name": "pop — 孟菲斯波普 (memphis-pop)",
    "bg": "#fef6e8",
    "text": "#111111",
    "anchor": "#ff3d8b",
    "description": "html-ppt-skill memphis-pop（浅色）",
}


MIDCENTURY = {
    "name": "世纪中期现代 (midcentury)",
    "bg": "#f3ead8",
    "text": "#201810",
    "anchor": "#d4902a",
    "description": "html-ppt-skill midcentury（浅色）",
}


MINIMALWHITE = {
    "name": "white — 极简白，克制高级 (minimal-white)",
    "bg": "#ffffff",
    "text": "#0c0d10",
    "anchor": "#111216",
    "description": "html-ppt-skill minimal-white（浅色）",
}


NEOBRUTALISM = {
    "name": "brutalism — 厚描边、硬阴影、明黄 (neo-brutalism)",
    "bg": "#fffef0",
    "text": "#000000",
    "anchor": "#ffd400",
    "description": "html-ppt-skill neo-brutalism（浅色）",
}


NEWSBROADCAST = {
    "name": "broadcast — 新闻播报 (news-broadcast)",
    "bg": "#ffffff",
    "text": "#0a0a0a",
    "anchor": "#e11d2d",
    "description": "html-ppt-skill news-broadcast（浅色）",
}


NORD = {
    "name": "nord (nord)",
    "bg": "#2e3440",
    "text": "#eceff4",
    "anchor": "#88c0d0",
    "description": "html-ppt-skill nord（深色）",
}


PITCHDECKVC = {
    "name": "deck-vc — YC 风融资 pitch (pitch-deck-vc)",
    "bg": "#ffffff",
    "text": "#0b0d12",
    "anchor": "#0070f3",
    "description": "html-ppt-skill pitch-deck-vc（浅色）",
}


RAINBOWGRADIENT = {
    "name": "gradient — 彩虹渐变点缀（白底） (rainbow-gradient)",
    "bg": "#ffffff",
    "text": "#0c0d10",
    "anchor": "#ff4d8b",
    "description": "html-ppt-skill rainbow-gradient（浅色）",
}


RETROTV = {
    "name": "tv — 复古显像管 (retro-tv)",
    "bg": "#f5ecd7",
    "text": "#2a1a08",
    "anchor": "#e67e14",
    "description": "html-ppt-skill retro-tv（浅色）",
}


ROSEPINE = {
    "name": "pine (rose-pine)",
    "bg": "#191724",
    "text": "#e0def4",
    "anchor": "#ebbcba",
    "description": "html-ppt-skill rose-pine（深色）",
}


SHARPMONO = {
    "name": "mono — 锐利黑白高对比 (sharp-mono)",
    "bg": "#ffffff",
    "text": "#000000",
    "anchor": "#000000",
    "description": "html-ppt-skill sharp-mono（浅色）",
}


SOFTPASTEL = {
    "name": "pastel — 柔和马卡龙 (soft-pastel)",
    "bg": "#fdf7fb",
    "text": "#3a1f33",
    "anchor": "#f49bb8",
    "description": "html-ppt-skill soft-pastel（浅色）",
}


SOLARIZEDLIGHT = {
    "name": "light (solarized-light)",
    "bg": "#fdf6e3",
    "text": "#073642",
    "anchor": "#268bd2",
    "description": "html-ppt-skill solarized-light（浅色）",
}


SUNSETWARM = {
    "name": "warm — 暖色调 橘/珊瑚/琥珀 (sunset-warm)",
    "bg": "#fff7ef",
    "text": "#2a160a",
    "anchor": "#e36a2d",
    "description": "html-ppt-skill sunset-warm（浅色）",
}


SWISSGRID = {
    "name": "grid — 瑞士网格，Helvetica 感 (swiss-grid)",
    "bg": "#ffffff",
    "text": "#111111",
    "anchor": "#d6001c",
    "description": "html-ppt-skill swiss-grid（浅色）",
}


TERMINALGREEN = {
    "name": "green — 绿屏终端 (terminal-green)",
    "bg": "#030a04",
    "text": "#8cff9a",
    "anchor": "#00ff88",
    "description": "html-ppt-skill terminal-green（深色）",
}


TOKYONIGHT = {
    "name": "night (tokyo-night)",
    "bg": "#1a1b26",
    "text": "#c0caf5",
    "anchor": "#7aa2f7",
    "description": "html-ppt-skill tokyo-night（深色）",
}


VAPORWAVE = {
    "name": "蒸汽波 (vaporwave)",
    "bg": "#1a0938",
    "text": "#fdf0ff",
    "anchor": "#ff6ec7",
    "description": "html-ppt-skill vaporwave（深色）",
}


XIAOHONGSHUWHITE = {
    "name": "white — 小红书白底高级感 (xiaohongshu-white)",
    "bg": "#fffdfb",
    "text": "#1a1210",
    "anchor": "#ff2742",
    "description": "html-ppt-skill xiaohongshu-white（浅色）",
}


Y2KCHROME = {
    "name": "chrome — 千禧银色铬金属 (y2k-chrome)",
    "bg": "#dfe4ec",
    "text": "#1a1f2e",
    "anchor": "#8a5cff",
    "description": "html-ppt-skill y2k-chrome（浅色）",
}


THEME_MAP.update({
    "academic-paper": ACADEMICPAPER,
    "arctic-cool": ARCTICCOOL,
    "aurora": AURORA,
    "bauhaus": BAUHAUS,
    "blueprint": BLUEPRINT,
    "catppuccin-latte": CATPPUCCINLATTE,
    "catppuccin-mocha": CATPPUCCINMOCHA,
    "corporate-clean": CORPORATECLEAN,
    "cyberpunk-neon": CYBERPUNKNEON,
    "dracula": DRACULA,
    "editorial-serif": EDITORIALSERIF,
    "engineering-whiteprint": ENGINEERINGWHITEPRINT,
    "glassmorphism": GLASSMORPHISM,
    "gruvbox-dark": GRUVBOXDARK,
    "japanese-minimal": JAPANESEMINIMAL,
    "magazine-bold": MAGAZINEBOLD,
    "memphis-pop": MEMPHISPOP,
    "midcentury": MIDCENTURY,
    "minimal-white": MINIMALWHITE,
    "neo-brutalism": NEOBRUTALISM,
    "news-broadcast": NEWSBROADCAST,
    "nord": NORD,
    "pitch-deck-vc": PITCHDECKVC,
    "rainbow-gradient": RAINBOWGRADIENT,
    "retro-tv": RETROTV,
    "rose-pine": ROSEPINE,
    "sharp-mono": SHARPMONO,
    "soft-pastel": SOFTPASTEL,
    "solarized-light": SOLARIZEDLIGHT,
    "sunset-warm": SUNSETWARM,
    "swiss-grid": SWISSGRID,
    "terminal-green": TERMINALGREEN,
    "tokyo-night": TOKYONIGHT,
    "vaporwave": VAPORWAVE,
    "xiaohongshu-white": XIAOHONGSHUWHITE,
    "y2k-chrome": Y2KCHROME,
})
