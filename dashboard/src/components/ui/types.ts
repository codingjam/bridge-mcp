// UI Library Abstraction Layer
// This file defines the interface for all UI components
// Implementation can be swapped by changing the imports

export interface ButtonProps {
  children?: React.ReactNode;
  type?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'text';
  size?: 'small' | 'medium' | 'large';
  icon?: React.ReactNode;
  loading?: boolean;
  disabled?: boolean;
  block?: boolean;
  onClick?: () => void;
  className?: string;
}

export interface CardProps {
  children: React.ReactNode;
  title?: string;
  extra?: React.ReactNode;
  loading?: boolean;
  className?: string;
  bodyStyle?: React.CSSProperties;
}

export interface TableColumn<T = any> {
  key: string;
  title: string;
  dataIndex?: keyof T;
  render?: (value: any, record: T, index: number) => React.ReactNode;
  width?: number | string;
  sorter?: boolean;
  align?: 'left' | 'center' | 'right';
}

export interface TableProps<T = any> {
  dataSource: T[];
  columns: TableColumn<T>[];
  loading?: boolean;
  pagination?: boolean | PaginationProps;
  rowKey?: string | ((record: T) => string);
  size?: 'small' | 'medium' | 'large';
  className?: string;
  onRow?: (record: T) => any;
}

export interface PaginationProps {
  current?: number;
  pageSize?: number;
  total?: number;
  showSizeChanger?: boolean;
  showQuickJumper?: boolean;
  onChange?: (page: number, pageSize: number) => void;
}

export interface FormProps {
  children: React.ReactNode;
  layout?: 'horizontal' | 'vertical' | 'inline';
  onFinish?: (values: any) => void;
  onFinishFailed?: (errorInfo: any) => void;
  initialValues?: any;
  className?: string;
}

export interface FormItemProps {
  children: React.ReactNode;
  label?: string;
  name?: string;
  rules?: any[];
  required?: boolean;
  className?: string;
}

export interface InputProps {
  value?: string;
  defaultValue?: string;
  placeholder?: string;
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
  prefix?: React.ReactNode;
  suffix?: React.ReactNode;
  onChange?: (value: string) => void;
  onPressEnter?: () => void;
  className?: string;
}

export interface SelectProps {
  value?: string | string[];
  defaultValue?: string | string[];
  placeholder?: string;
  options: Array<{ label: string; value: string; disabled?: boolean }>;
  multiple?: boolean;
  disabled?: boolean;
  loading?: boolean;
  allowClear?: boolean;
  showSearch?: boolean;
  onChange?: (value: string | string[]) => void;
  className?: string;
}

export interface ModalProps {
  children: React.ReactNode;
  title?: string;
  open?: boolean;
  width?: number | string;
  footer?: React.ReactNode | null;
  onOk?: () => void;
  onCancel?: () => void;
  confirmLoading?: boolean;
  destroyOnClose?: boolean;
  className?: string;
}

export interface AlertProps {
  message: string;
  description?: string;
  type: 'success' | 'info' | 'warning' | 'error';
  showIcon?: boolean;
  closable?: boolean;
  onClose?: () => void;
  className?: string;
}

export interface BadgeProps {
  children?: React.ReactNode;
  count?: number | string;
  dot?: boolean;
  status?: 'success' | 'processing' | 'default' | 'error' | 'warning';
  text?: string;
  className?: string;
  size?: 'default' | 'small';
}

export interface MenuProps {
  items: MenuItem[];
  mode?: 'horizontal' | 'vertical' | 'inline';
  theme?: 'light' | 'dark';
  selectedKeys?: string[];
  openKeys?: string[];
  onClick?: (info: { key: string }) => void;
  onOpenChange?: (openKeys: string[]) => void;
  className?: string;
}

export interface MenuItem {
  key: string;
  label: string | React.ReactNode;
  icon?: React.ReactNode;
  children?: MenuItem[];
  disabled?: boolean;
  danger?: boolean;
}

export interface StatisticProps {
  title: string;
  value: number | string;
  prefix?: React.ReactNode;
  suffix?: string;
  precision?: number;
  loading?: boolean;
  valueStyle?: React.CSSProperties;
  className?: string;
}

export interface SpinProps {
  spinning?: boolean;
  size?: 'small' | 'medium' | 'large';
  tip?: string;
  children?: React.ReactNode;
  className?: string;
}

export interface LayoutProps {
  children: React.ReactNode;
  className?: string;
}

export interface HeaderProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export interface SiderProps {
  children: React.ReactNode;
  collapsed?: boolean;
  collapsible?: boolean;
  trigger?: React.ReactNode | null;
  width?: number | string;
  className?: string;
}

export interface ContentProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export interface AvatarProps {
  size?: 'small' | 'default' | 'large' | number;
  icon?: React.ReactNode;
  src?: string;
  alt?: string;
  className?: string;
}

export interface DropdownProps {
  children: React.ReactNode;
  menu: { items: MenuProps['items'] };
  placement?: 'bottomLeft' | 'bottomRight' | 'topLeft' | 'topRight';
  trigger?: ('click' | 'hover')[];
  className?: string;
}

export interface SpaceProps {
  children: React.ReactNode;
  size?: 'small' | 'middle' | 'large' | number;
  direction?: 'vertical' | 'horizontal';
  className?: string;
  align?: 'start' | 'end' | 'center' | 'baseline';
}

export interface TypographyProps {
  children: React.ReactNode;
  className?: string;
  strong?: boolean;
  type?: 'secondary' | 'success' | 'warning' | 'danger';
}

export interface TextProps extends TypographyProps {}

export interface TitleProps extends TypographyProps {
  level?: 1 | 2 | 3 | 4 | 5;
}
