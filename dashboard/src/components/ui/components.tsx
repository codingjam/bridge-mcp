// Ant Design Implementation of UI Components
// To swap UI libraries, only change the imports and implementations in this file

import React from 'react';
import {
  Button as AntButton,
  Card as AntCard,
  Table as AntTable,
  Form as AntForm,
  Input as AntInput,
  Select as AntSelect,
  Modal as AntModal,
  Alert as AntAlert,
  Badge as AntBadge,
  Menu as AntMenu,
  Statistic as AntStatistic,
  Spin as AntSpin,
  Layout as AntLayout,
  Avatar as AntAvatar,
  Dropdown as AntDropdown,
  Space as AntSpace,
  Typography as AntTypography,
} from 'antd';

import type {
  ButtonProps,
  CardProps,
  TableProps,
  FormProps,
  FormItemProps,
  InputProps,
  SelectProps,
  ModalProps,
  AlertProps,
  BadgeProps,
  MenuProps,
  StatisticProps,
  SpinProps,
  LayoutProps,
  HeaderProps,
  SiderProps,
  ContentProps,
  AvatarProps,
  DropdownProps,
  SpaceProps,
  TextProps,
  TitleProps,
} from './types';

// Button Component
export const Button: React.FC<ButtonProps> = ({
  children,
  type = 'primary',
  size = 'medium',
  icon,
  loading,
  disabled,
  block,
  onClick,
  className,
}) => {
  const antType = type === 'secondary' ? 'default' : 
                  type === 'danger' ? 'primary' : 
                  type === 'ghost' ? 'ghost' : 
                  type === 'text' ? 'text' : 'primary';
  
  const antSize = size === 'medium' ? 'middle' : size === 'small' ? 'small' : 'large';

  return (
    <AntButton
      type={antType as any}
      size={antSize as any}
      icon={icon}
      loading={loading}
      disabled={disabled}
      block={block}
      onClick={onClick}
      className={className}
      danger={type === 'danger'}
    >
      {children}
    </AntButton>
  );
};

// Card Component
export const Card: React.FC<CardProps> = ({
  children,
  title,
  extra,
  loading,
  className,
  bodyStyle,
}) => (
  <AntCard
    title={title}
    extra={extra}
    loading={loading}
    className={className}
    bodyStyle={bodyStyle}
  >
    {children}
  </AntCard>
);

// Table Component
export const Table: React.FC<TableProps> = ({
  dataSource,
  columns,
  loading,
  pagination,
  rowKey,
  size = 'medium',
  className,
  onRow,
}) => {
  const antSize = size === 'medium' ? 'middle' : size === 'small' ? 'small' : 'default';
  
  return (
    <AntTable
      dataSource={dataSource}
      columns={columns as any}
      loading={loading}
      pagination={pagination as any}
      rowKey={rowKey}
      size={antSize as any}
      className={className}
      onRow={onRow}
    />
  );
};

// Form Components
export const Form: React.FC<FormProps> = ({
  children,
  layout = 'vertical',
  onFinish,
  onFinishFailed,
  initialValues,
  className,
}) => (
  <AntForm
    layout={layout}
    onFinish={onFinish}
    onFinishFailed={onFinishFailed}
    initialValues={initialValues}
    className={className}
  >
    {children}
  </AntForm>
);

export const FormItem: React.FC<FormItemProps> = ({
  children,
  label,
  name,
  rules,
  required,
  className,
}) => (
  <AntForm.Item
    label={label}
    name={name}
    rules={rules}
    required={required}
    className={className}
  >
    {children}
  </AntForm.Item>
);

// Input Component
export const Input: React.FC<InputProps> = ({
  value,
  defaultValue,
  placeholder,
  size = 'medium',
  disabled,
  prefix,
  suffix,
  onChange,
  onPressEnter,
  className,
}) => {
  const antSize = size === 'medium' ? 'middle' : size === 'small' ? 'small' : 'large';

  return (
    <AntInput
      value={value}
      defaultValue={defaultValue}
      placeholder={placeholder}
      size={antSize as any}
      disabled={disabled}
      prefix={prefix}
      suffix={suffix}
      onChange={(e) => onChange?.(e.target.value)}
      onPressEnter={onPressEnter}
      className={className}
    />
  );
};

// Select Component
export const Select: React.FC<SelectProps> = ({
  value,
  defaultValue,
  placeholder,
  options,
  multiple,
  disabled,
  loading,
  allowClear,
  showSearch,
  onChange,
  className,
}) => (
  <AntSelect
    value={value}
    defaultValue={defaultValue}
    placeholder={placeholder}
    options={options}
    mode={multiple ? 'multiple' : undefined}
    disabled={disabled}
    loading={loading}
    allowClear={allowClear}
    showSearch={showSearch}
    onChange={onChange}
    className={className}
  />
);

// Modal Component
export const Modal: React.FC<ModalProps> = ({
  children,
  title,
  open,
  width,
  footer,
  onOk,
  onCancel,
  confirmLoading,
  destroyOnClose,
  className,
}) => (
  <AntModal
    title={title}
    open={open}
    width={width}
    footer={footer}
    onOk={onOk}
    onCancel={onCancel}
    confirmLoading={confirmLoading}
    destroyOnClose={destroyOnClose}
    className={className}
  >
    {children}
  </AntModal>
);

// Alert Component
export const Alert: React.FC<AlertProps> = ({
  message,
  description,
  type,
  showIcon,
  closable,
  onClose,
  className,
}) => (
  <AntAlert
    message={message}
    description={description}
    type={type}
    showIcon={showIcon}
    closable={closable}
    onClose={onClose}
    className={className}
  />
);

// Badge Component
export const Badge: React.FC<BadgeProps> = ({
  children,
  count,
  dot,
  status,
  text,
  className,
  size = 'default',
}) => (
  <AntBadge
    count={count}
    dot={dot}
    status={status}
    text={text}
    className={className}
    size={size as any}
  >
    {children}
  </AntBadge>
);

// Menu Component
export const Menu: React.FC<MenuProps> = ({
  items,
  mode = 'vertical',
  theme = 'light',
  selectedKeys,
  openKeys,
  onClick,
  onOpenChange,
  className,
}) => (
  <AntMenu
    items={items as any}
    mode={mode}
    theme={theme}
    selectedKeys={selectedKeys}
    openKeys={openKeys}
    onClick={onClick}
    onOpenChange={onOpenChange}
    className={className}
  />
);

// Statistic Component
export const Statistic: React.FC<StatisticProps> = ({
  title,
  value,
  prefix,
  suffix,
  precision,
  loading,
  valueStyle,
  className,
}) => (
  <AntStatistic
    title={title}
    value={value}
    prefix={prefix}
    suffix={suffix}
    precision={precision}
    loading={loading}
    valueStyle={valueStyle}
    className={className}
  />
);

// Spin Component
export const Spin: React.FC<SpinProps> = ({
  spinning = true,
  size = 'medium',
  tip,
  children,
  className,
}) => {
  const antSize = size === 'medium' ? 'default' : size === 'small' ? 'small' : 'large';

  return (
    <AntSpin
      spinning={spinning}
      size={antSize as any}
      tip={tip}
      className={className}
    >
      {children}
    </AntSpin>
  );
};

// Layout Components
export const Layout: React.FC<LayoutProps> = ({ children, className }) => (
  <AntLayout className={className}>{children}</AntLayout>
);

export const Header: React.FC<HeaderProps> = ({ children, className, style }) => (
  <AntLayout.Header className={className} style={style}>
    {children}
  </AntLayout.Header>
);

export const Sider: React.FC<SiderProps> = ({
  children,
  collapsed,
  collapsible,
  trigger,
  width,
  className,
}) => (
  <AntLayout.Sider
    collapsed={collapsed}
    collapsible={collapsible}
    trigger={trigger}
    width={width}
    className={className}
  >
    {children}
  </AntLayout.Sider>
);

export const Content: React.FC<ContentProps> = ({ children, className, style }) => (
  <AntLayout.Content className={className} style={style}>
    {children}
  </AntLayout.Content>
);

// Avatar Component
export const Avatar: React.FC<AvatarProps> = ({
  size = 'default',
  icon,
  src,
  alt,
  className,
}) => (
  <AntAvatar
    size={size}
    icon={icon}
    src={src}
    alt={alt}
    className={className}
  />
);

// Dropdown Component
export const Dropdown: React.FC<DropdownProps> = ({
  children,
  menu,
  placement = 'bottomLeft',
  trigger = ['hover'],
  className,
}) => (
  <AntDropdown
    menu={menu as any}
    placement={placement}
    trigger={trigger}
    className={className}
  >
    {children}
  </AntDropdown>
);

// Space Component
export const Space: React.FC<SpaceProps> = ({
  children,
  size = 'small',
  direction = 'horizontal',
  className,
  align,
}) => (
  <AntSpace
    size={size}
    direction={direction}
    className={className}
    align={align}
  >
    {children}
  </AntSpace>
);

// Typography Components
export const Typography = {
  Text: ({ children, className, strong, type }: TextProps) => (
    <AntTypography.Text className={className} strong={strong} type={type}>
      {children}
    </AntTypography.Text>
  ),
  Title: ({ children, className, level = 1 }: TitleProps) => (
    <AntTypography.Title className={className} level={level}>
      {children}
    </AntTypography.Title>
  ),
};

// Re-export types for convenience
export type { ButtonProps, CardProps, TableProps, TableColumn } from './types';
