import { useEffect, useState } from "react";
import {
  Card,
  Form,
  Input,
  Button,
  Tabs,
  Table,
  Tag,
  Space,
  Typography,
  Modal,
  message,
  Descriptions,
  Spin,
} from "antd";
import { ArrowLeftOutlined, PlusOutlined, CopyOutlined } from "@ant-design/icons";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import type { Broker, User, AdminRole } from "../../types";
import {
  getPlatformBroker,
  createPlatformBroker,
  updatePlatformBroker,
  createBrokerAdmin,
  getBrokerAdmins,
} from "../../api/endpoints";

export default function BrokerForm() {
  const { id } = useParams();
  const isNew = id === "new";
  const navigate = useNavigate();
  const location = useLocation();
  const [form] = Form.useForm();
  const [broker, setBroker] = useState<Broker | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [admins, setAdmins] = useState<User[]>([]);
  const [adminModalOpen, setAdminModalOpen] = useState(false);
  const [adminForm] = Form.useForm();
  const [activeTab, setActiveTab] = useState(
    (location.state as { tab?: string })?.tab || "details"
  );

  useEffect(() => {
    if (!isNew && id) {
      fetchBroker(Number(id));
      fetchAdmins(Number(id));
    }
  }, [id]);

  const fetchBroker = async (brokerId: number) => {
    setLoading(true);
    try {
      const res = await getPlatformBroker(brokerId);
      setBroker(res.data);
      form.setFieldsValue(res.data);
    } catch {
      message.error("Failed to load broker");
      navigate("/");
    } finally {
      setLoading(false);
    }
  };

  const fetchAdmins = async (brokerId: number) => {
    try {
      const res = await getBrokerAdmins(brokerId);
      setAdmins(res.data);
    } catch {
      // ignore
    }
  };

  const handleSave = async (values: Record<string, string>) => {
    setSaving(true);
    try {
      if (isNew) {
        const res = await createPlatformBroker(values as any);
        message.success("Broker created");
        navigate(`/brokers/${res.data.id}`);
      } else {
        await updatePlatformBroker(Number(id), values as any);
        message.success("Broker updated");
        fetchBroker(Number(id));
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleCreateAdmin = async (values: { email: string; password: string; full_name: string }) => {
    try {
      await createBrokerAdmin(Number(id), values);
      message.success("Broker admin created");
      setAdminModalOpen(false);
      adminForm.resetFields();
      fetchAdmins(Number(id));
    } catch (err: any) {
      message.error(err.response?.data?.detail || "Failed to create admin");
    }
  };

  const copyApiKey = () => {
    if (broker?.api_key) {
      navigator.clipboard.writeText(broker.api_key);
      message.success("API key copied");
    }
  };

  if (loading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;

  const adminColumns = [
    { title: "Name", dataIndex: "full_name", key: "full_name" },
    { title: "Email", dataIndex: "email", key: "email" },
    {
      title: "Role",
      dataIndex: "role",
      key: "role",
      render: (r: AdminRole) => r.replace("_", " ").toUpperCase(),
    },
    {
      title: "Type",
      key: "type",
      render: (_: unknown, record: User) =>
        record.is_broker_admin ? (
          <Tag color="blue">Broker Admin</Tag>
        ) : (
          <Tag>Sub-Admin</Tag>
        ),
    },
    {
      title: "Status",
      key: "status",
      render: (_: unknown, record: User) =>
        record.is_active ? <Tag color="green">Active</Tag> : <Tag color="red">Inactive</Tag>,
    },
  ];

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/")}>
          Back
        </Button>
        <Typography.Title level={3} style={{ margin: 0 }}>
          {isNew ? "New Broker" : broker?.name}
        </Typography.Title>
      </Space>

      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <Tabs.TabPane tab="Details" key="details">
          <Card>
            <Form form={form} layout="vertical" onFinish={handleSave} style={{ maxWidth: 600 }}>
              <Form.Item label="Name" name="name" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item
                label="Slug"
                name="slug"
                rules={[{ required: true }]}
                extra="Used as subdomain: slug.yourdomain.com"
              >
                <Input disabled={!isNew} />
              </Form.Item>
              <Form.Item label="Contact Email" name="contact_email">
                <Input type="email" />
              </Form.Item>
              <Form.Item label="Contact Phone" name="contact_phone">
                <Input />
              </Form.Item>

              <Typography.Title level={5}>MT5 Configuration</Typography.Title>
              <Form.Item label="Bridge URL" name="mt5_bridge_url">
                <Input placeholder="http://bridge-host:5000" />
              </Form.Item>
              <Form.Item label="MT5 Server" name="mt5_server">
                <Input placeholder="173.234.17.76" />
              </Form.Item>
              <Form.Item label="Manager Login" name="mt5_manager_login">
                <Input />
              </Form.Item>
              <Form.Item label="Manager Password" name="mt5_manager_password">
                <Input.Password placeholder={isNew ? "" : "Leave blank to keep current"} />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit" loading={saving}>
                  {isNew ? "Create Broker" : "Save Changes"}
                </Button>
              </Form.Item>
            </Form>
          </Card>

          {!isNew && broker && (
            <Card title="Broker Info" style={{ marginTop: 16 }}>
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="ID">{broker.id}</Descriptions.Item>
                <Descriptions.Item label="Status">
                  {broker.is_active ? (
                    <Tag color="green">Active</Tag>
                  ) : (
                    <Tag color="red">Inactive</Tag>
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="MT5 Connected">
                  {broker.mt5_configured ? (
                    <Tag color="green">Yes</Tag>
                  ) : (
                    <Tag>No</Tag>
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="API Key">
                  {broker.api_key ? (
                    <Space>
                      <code>{broker.api_key}</code>
                      <Button size="small" icon={<CopyOutlined />} onClick={copyApiKey} />
                    </Space>
                  ) : (
                    "N/A"
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="Created">
                  {new Date(broker.created_at).toLocaleString()}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          )}
        </Tabs.TabPane>

        {!isNew && (
          <Tabs.TabPane tab="Admin Users" key="admins">
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <Typography.Title level={4} style={{ margin: 0 }}>
                Admin Users
              </Typography.Title>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setAdminModalOpen(true)}
              >
                Create Broker Admin
              </Button>
            </div>
            <Table columns={adminColumns} dataSource={admins} rowKey="id" pagination={false} />
          </Tabs.TabPane>
        )}
      </Tabs>

      <Modal
        title="Create Broker Admin"
        open={adminModalOpen}
        onCancel={() => setAdminModalOpen(false)}
        footer={null}
      >
        <Form form={adminForm} layout="vertical" onFinish={handleCreateAdmin}>
          <Form.Item label="Full Name" name="full_name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Email" name="email" rules={[{ required: true, type: "email" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Password" name="password" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              Create
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
