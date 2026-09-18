import { Row, Col, Card, Listy, Button, Typography, App } from 'antd';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { dashboardApi } from '../api/dashboard';
import { useTerms } from '../hooks/useTerms';
import { errMsg } from '../api/http';

export default function Immune() {
  const { t } = useTerms();
  const { message, modal } = App.useApp();
  const qc = useQueryClient();

  const { data: d } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.dashboard,
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ['dashboard'] });

  const removeTolerance = async (sig: string) => {
    try {
      await dashboardApi.toleranceRemove(sig);
      refresh();
    } catch (e) {
      message.error(errMsg(e));
    }
  };
  const clearTolerance = () => {
    modal.confirm({
      title: '清空免疫耐受白名单？',
      onOk: async () => {
        await dashboardApi.toleranceClear();
        refresh();
      },
    });
  };
  const removeInnate = async (sig: string) => {
    try {
      await dashboardApi.innateRemove(sig);
      refresh();
    } catch (e) {
      message.error(errMsg(e));
    }
  };
  const clearInnate = () => {
    modal.confirm({
      title: '清空固有免疫规则？',
      onOk: async () => {
        await dashboardApi.innateClear();
        refresh();
      },
    });
  };

  const tolerance = d?.tolerance ?? [];
  const innate = d?.innate ?? [];

  const renderSigList = (items: string[], onRemove: (s: string) => void) => (
    <div style={{ maxHeight: 520, overflowY: 'auto', paddingRight: 8 }}>
      {items.length === 0 ? (
        <Typography.Text type="secondary">空</Typography.Text>
      ) : (
        <Listy<string>
          items={items}
          rowKey={(sig) => sig}
          itemRender={(sig) => (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '6px 0' }}>
              <Typography.Text code style={{ wordBreak: 'break-all', whiteSpace: 'pre-wrap', flex: 1 }}>{sig}</Typography.Text>
              <Button type="text" danger size="small" onClick={() => onRemove(sig)}>删除</Button>
            </div>
          )}
        />
      )}
    </div>
  );

  return (
    <div>
      <Typography.Title level={4}>{t('immuneTitle')}</Typography.Title>
      <Typography.Paragraph type="secondary">{t('tolerance')} · {t('innate')}</Typography.Paragraph>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card
            size="small"
            title={`${t('tolerance')}（已知好 → 静默）`}
            extra={<Button size="small" danger onClick={clearTolerance}>清空</Button>}
          >
            <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
              按签名匹配（掩码 IP/哈希/数字）；命中即静默，连杏仁核都不叫。
            </Typography.Paragraph>
            {renderSigList(tolerance, removeTolerance)}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card
            size="small"
            title={`${t('innate')}（已知坏 → 秒拦）`}
            extra={<Button size="small" danger onClick={clearInnate}>清空</Button>}
          >
            <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
              命中即边缘秒拦（conf 0.95），前额叶不醒。
            </Typography.Paragraph>
            {renderSigList(innate, removeInnate)}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
