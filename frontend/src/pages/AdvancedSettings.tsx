import { Card, Empty, Typography } from 'antd';

export default function AdvancedSettings() {
  return (
    <Card>
      <Typography.Title level={4} style={{ marginTop: 0 }}>高级设置</Typography.Title>
      <Empty description="开发中（M3 实现）" />
    </Card>
  );
}
