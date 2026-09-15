import {useCurrentFrame} from 'remotion';
import {interpolate} from 'remotion';

interface Props {
  shot: any;
  tokens: any;
}

export function MapCard({shot, tokens}: Props) {
  const frame = useCurrentFrame();

  // 提取地点信息（简化版：从 visual 提取关键词）
  const location = shot.visual.match(/(?:在|于|到达|前往)([^，。！？]{2,10})(?:市|省|国|岛|湾|海|山|江)/)?.[1] || '示例地点';

  // 模拟多个标注点
  const pins = [
    {x: 0.3, y: 0.4, label: '起点'},
    {x: 0.6, y: 0.3, label: '中转'},
    {x: 0.8, y: 0.6, label: '终点'},
  ];

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        background: tokens.bg,
        color: tokens.text,
        padding: 40,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* 地图容器 */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: '60%',
          background: `${tokens.anchor}10`,
          borderRadius: 16,
          border: `2px solid ${tokens.anchor}40`,
          overflow: 'hidden',
        }}
      >
        {/* 模拟地图网格 */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: `
              linear-gradient(${tokens.anchor}20 1px, transparent 1px),
              linear-gradient(90deg, ${tokens.anchor}20 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px',
          }}
        />

        {/* 模拟陆地形状 */}
        <div
          style={{
            position: 'absolute',
            top: '20%',
            left: '15%',
            width: '70%',
            height: '60%',
            background: `${tokens.text}15`,
            borderRadius: '40% 60% 50% 40%',
            filter: 'blur(20px)',
          }}
        />

        {/* 标注点 */}
        {pins.map((pin, i) => {
          const delay = 20 + i * 15;
          const scale = frame > delay ? 1 : 0;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: `${pin.x * 100}%`,
                top: `${pin.y * 100}%`,
                transform: 'translate(-50%, -50%)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 8,
                opacity: scale,
                transition: 'all 0.5s',
              }}
            >
              {/* Pin 图标 */}
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50% 50% 50% 0',
                  background: tokens.anchor,
                  transform: 'rotate(-45deg)',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    background: tokens.bg,
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                  }}
                />
              </div>

              {/* 标签 */}
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: tokens.anchor,
                  background: `${tokens.bg}90`,
                  padding: '4px 10px',
                  borderRadius: 8,
                }}
              >
                {pin.label}
              </div>
            </div>
          );
        })}

        {/* 连线（简化版：静态 SVG） */}
        <svg
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            opacity: frame > 50 ? 0.6 : 0,
            transition: 'opacity 0.5s',
          }}
        >
          <path
            d={`M ${pins[0].x * 100}% ${pins[0].y * 100}% L ${pins[1].x * 100}% ${pins[1].y * 100}% L ${pins[2].x * 100}% ${pins[2].y * 100}%`}
            stroke={tokens.anchor}
            strokeWidth="3"
            fill="none"
            strokeDasharray="8, 4"
          />
        </svg>
      </div>

      {/* 地点标题 */}
      <div
        style={{
          marginTop: 32,
          fontSize: 36,
          fontWeight: 800,
          color: tokens.anchor,
          textAlign: 'center',
        }}
      >
        {location}
      </div>

      {/* 说明文字 */}
      {shot.vo && (
        <div
          style={{
            marginTop: 16,
            fontSize: 18,
            fontWeight: 500,
            color: tokens.text,
            opacity: 0.7,
            textAlign: 'center',
            maxWidth: '80%',
          }}
        >
          {shot.vo.slice(0, 50)}
        </div>
      )}
    </div>
  );
}