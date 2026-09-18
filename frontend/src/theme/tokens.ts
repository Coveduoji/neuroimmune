import type { ThemeConfig } from 'antd';

// 把旧 index.css 的 20 个 CSS token 映射为 antd 主题 token。
const shared = {
  borderRadius: 8,
  fontFamily:
    "system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
};

export const lightTheme: ThemeConfig = {
  token: {
    ...shared,
    colorPrimary: '#2a78d6',
    colorError: '#d03b3b',
    colorWarning: '#b7791f',
    colorSuccess: '#1baf7a',
    colorBgLayout: '#f5f6f8',
    colorBgContainer: '#ffffff',
    colorText: '#0b0b0b',
    colorTextSecondary: '#4d5158',
    colorTextTertiary: '#8a8f98',
    colorBorder: '#e4e7eb',
    colorBorderSecondary: '#eef0f3',
  },
};

export const darkTheme: ThemeConfig = {
  token: {
    ...shared,
    colorPrimary: '#3987e5',
    colorError: '#e66767',
    colorWarning: '#d8a24a',
    colorSuccess: '#34c28b',
    colorBgLayout: '#0e1013',
    colorBgContainer: '#1a1e23',
    colorText: '#f2f4f7',
    colorTextSecondary: '#b8bec8',
    colorTextTertiary: '#8a919c',
    colorBorder: '#2a2f36',
    colorBorderSecondary: '#15181c',
  },
};

// 实体图节点四色（asset/ip/hash/domain），固定不随主题变，保证图可读性。
export const ENTITY_COLORS: Record<string, string> = {
  asset: '#2a78d6',
  ip: '#1baf7a',
  hash: '#d03b3b',
  domain: '#b7791f',
};
