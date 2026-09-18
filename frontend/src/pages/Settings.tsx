import { Card, Empty, Typography } from 'antd';
import { useTerms } from '../hooks/useTerms';

export default function Settings() {
  const { t } = useTerms();
  return (
    <Card>
      <Typography.Title level={4} style={{ marginTop: 0 }}>{t('settings')}</Typography.Title>
      <Empty description="开发中（M3 实现）" />
    </Card>
  );
}
