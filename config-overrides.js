const { override, addWebpackAlias } = require('customize-cra');
const path = require('path');

module.exports = override(
    // 删除了 fixBabelImports 部分，因为 antd v5+ 不需要它
    addWebpackAlias({
        '@': path.resolve(__dirname, 'src'),
        '@components': path.resolve(__dirname, 'src/components'),
        '@utils': path.resolve(__dirname, 'src/utils'),
        '@hooks': path.resolve(__dirname, 'src/hooks'),
    })
);