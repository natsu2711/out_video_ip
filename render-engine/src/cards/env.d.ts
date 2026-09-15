// webpack（Remotion bundler）的 require.context 类型声明。
// require 字面量必须保留——webpack 在构建期识别 require.context 做惰性打包。
declare const require: {
  context(path: string, deep: boolean, filter: RegExp): {
    keys(): string[];
    (id: string): any;
  };
};
