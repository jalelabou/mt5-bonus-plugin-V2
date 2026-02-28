import { useState } from "react";
import { Form, Input, Button, Card, Typography, message } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useBroker } from "../context/BrokerContext";

export default function Login() {
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const { isPlatform } = useBroker();
  const navigate = useNavigate();

  const onFinish = async (values: { email: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.email, values.password);
      message.success("Login successful");
      navigate("/");
    } catch {
      message.error("Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", background: "#f0f2f5" }}>
      <Card style={{ width: 400 }}>
        <Typography.Title level={2} style={{ textAlign: "center", marginBottom: 8 }}>
          {isPlatform ? "Platform Admin" : "MT5 Bonus"}
        </Typography.Title>
        <Typography.Text type="secondary" style={{ display: "block", textAlign: "center", marginBottom: 24 }}>
          {isPlatform ? "Manage brokers and platform settings" : "Campaign & bonus management"}
        </Typography.Text>
        <Form onFinish={onFinish} size="large">
          <Form.Item name="email" rules={[{ required: true, message: "Enter email" }]}>
            <Input prefix={<UserOutlined />} placeholder="Email" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "Enter password" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="Password" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Sign In
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
