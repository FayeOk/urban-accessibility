import React, { useState } from 'react';
import { Upload, Button, Progress, message, Space, Checkbox } from 'antd';
import { UploadOutlined, DeleteOutlined } from '@ant-design/icons';

const DataUpload = ({ geoData, onDataUpdate, showStops, onShowStopsChange }) => {
  const [loading, setLoading] = useState(false);
  const [percent, setPercent] = useState(0);

  // 统计逻辑
  const routes = geoData.features.filter(f => f.geometry?.type.includes('Line')).length;
  const stops = geoData.features.filter(f => f.geometry?.type === 'Point').length;

  const processFiles = async (fileList) => {
    setLoading(true);
    setPercent(0);
    let newFeatures = [];
    const total = fileList.length;

    try {
      for (let i = 0; i < total; i++) {
        const file = fileList[i];
        const text = await file.text();
        const json = JSON.parse(text);
        const features = json.type === 'FeatureCollection' ? json.features : [json];
        newFeatures = [...newFeatures, ...features];
        setPercent(Math.round(((i + 1) / total) * 100));
      }

      onDataUpdate(prev => ({
        type: 'FeatureCollection',
        features: [...(prev?.features || []), ...newFeatures]
      }));
      message.success(`成功导入 ${newFeatures.length} 个要素`);
    } catch (err) {
      message.error("文件解析失败，请检查 GeoJSON 格式");
    } finally {
      setLoading(false);
      setPercent(0);
    }
  };

  return (
    <div className="sidebar-content-wrapper" style={{ padding: '24px 16px' }}>
      <h3 style={{ color: '#fff', marginBottom: '20px' }}>公交网络管理</h3>

      <div className="data-row">
        <span>已加载线路</span>
        <span className="value">{routes} 条</span>
      </div>
      <div className="data-row">
        <span>已加载站点</span>
        <span className="value">{stops} 个</span>
      </div>

      <div className="custom-checkbox-row">
        <Checkbox
          checked={showStops}
          onChange={(e) => onShowStopsChange(e.target.checked)}
        >
          显示站点图层
        </Checkbox>
      </div>

      <Space direction="vertical" style={{ width: '100%', marginTop: '24px' }} size="middle">
        <Upload
          multiple
          beforeUpload={(file, list) => { if (file === list[0]) processFiles(list); return false; }}
          showUploadList={false}
        >
          <Button block type="primary" icon={<UploadOutlined />} loading={loading}>
            导入数据 (.geojson)
          </Button>
        </Upload>
        {loading && <Progress percent={percent} size="small" strokeColor="#3ea6ff" />}
        <Button block danger ghost icon={<DeleteOutlined />} onClick={() => onDataUpdate({ type: 'FeatureCollection', features: [] })}>
          清空视图
        </Button>
      </Space>
    </div>
  );
};

export default DataUpload;