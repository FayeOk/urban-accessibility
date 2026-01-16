#!/bin/bash
echo "开始修复项目..."

# 停止服务器
echo "停止服务器..."
kill -9 $(lsof -ti:3000) 2>/dev/null || true

# 清理缓存
echo "清理缓存..."
rm -rf node_modules/.cache

# 创建CSS文件
echo "创建缺失文件..."
mkdir -p src/styles src/components/Map src/components/Sidebar

files=(
  "src/components/Map/MapContainer.css"
  "src/components/Sidebar/SidebarPanel.css"
  "src/components/Sidebar/DataUpload.css"
  "src/components/Sidebar/AnalysisPanel.css"
  "src/styles/MainPage.css"
  "src/styles/index.css"
  "src/styles/App.css"
)

for file in "${files[@]}"; do
  if [ ! -f "$file" ]; then
    mkdir -p "$(dirname "$file")"
    echo "/* $(basename "$file" .css) */" > "$file"
    echo "✅ 创建: $file"
  else
    echo "📁 已存在: $file"
  fi
done

echo "🎉 修复完成！请运行: npm start"
