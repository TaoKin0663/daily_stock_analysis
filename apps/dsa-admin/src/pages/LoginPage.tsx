import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useEffect } from 'react'
import { useAdminData } from '../hooks/useAdminData'
import type { LoginValues } from '../types'

const { Title, Text } = Typography

export function LoginPage() {
  const { handleLogin, isFirstTimeSetup, loginError, loggingIn } = useAdminData()
  const [loginForm] = Form.useForm<LoginValues>()

  useEffect(() => {
    loginForm.setFieldValue('password', '')
    loginForm.setFieldValue('passwordConfirm', '')
  }, [loginForm])

  return (
    <div className="admin-login-page">
      <Card className="admin-login-card">
        <Title level={3} className="admin-login-title">
          DSA 管理后台登录
        </Title>
        <Text type="secondary">
          {isFirstTimeSetup ? '首次使用请设置管理后台登录密码。' : '请输入管理后台账号和密码。'}
        </Text>
        <Form form={loginForm} layout="vertical" className="admin-login-form" onFinish={(values) => void handleLogin(values)}>
          <Form.Item
            label="账号"
            name="username"
            rules={[{ required: true, message: '请输入账号' }]}
          >
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item
            label={isFirstTimeSetup ? '设置密码' : '密码'}
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password autoComplete={isFirstTimeSetup ? 'new-password' : 'current-password'} />
          </Form.Item>
          {isFirstTimeSetup ? (
            <Form.Item
              label="确认密码"
              name="passwordConfirm"
              rules={[{ required: true, message: '请再次输入密码' }]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
          ) : null}
          {loginError ? <Alert type="error" showIcon message={loginError} className="admin-login-alert" /> : null}
          <Button type="primary" htmlType="submit" block loading={loggingIn}>
            {isFirstTimeSetup ? '完成设置并登录' : '登录后台'}
          </Button>
        </Form>
      </Card>
    </div>
  )
}
