import {Config} from '@remotion/cli/config';

// Remotion 4 写法：Config 是带方法的对象，不是可调用函数
Config.overrideWebpackConfig((conf) => ({
  ...conf,
  resolve: {
    ...conf.resolve,
    modules: ['node_modules', ...((conf.resolve?.modules as string[]) || [])],
  },
}));

// 关闭 webpack 持久化缓存：实测缓存对源码变更的失效不可靠
// （改了镜头组件仍可能用旧 bundle），确定性优先，每次全量打包。
Config.setCachingEnabled(false);
