import { useEffect, useState } from "react";
import {
  Table,
  Button,
  Tag,
  Space,
  Typography,
  Modal,
  Form,
  Input,
  Select,
  Popconfirm,
  message,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { User, AdminRole } from "../../types";
import { getUsers, createUser, updateUser, deactivateUser } from "../../api/endpoints";

const ROLES: { value: AdminRole; label: string }[] = [
  { value: "super_admin", label: "Super Admin" },
  { value: "campaign_manager", label: "Campaign Manager" },
  { value: "support_agent", label: "Support Agent" },
  { value: "read_only", label: "Read Only" },
];

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await getUsers();
      setUsers(res.data);
    } catch {
      message.error("Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreate = async (values: { email: string; password: string; full_name: string; role: AdminRole }) => {
    try {
      await createUser(values);
      message.success("User created");
      setModalOpen(false);
      form.resetFields();
      fetchUsers();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "Failed to create user");
    }
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    editForm.setFieldsValue({ full_name: user.full_name, role: user.role });
  };

  const handleUpdate = async (values: { full_name: string; role: AdminRole }) => {
    if (!editingUser) return;
    try {
      await updateUser(editingUser.id, values);
      message.success("User updated");
      setEditingUser(null);
      fetchUsers();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "Failed to update user");
    }
  };

  const handleDeactivate = async (id: number) => {
    try {
      await deactivateUser(id);
      message.success("User deactivated");
      fetchUsers();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "Failed to deactivate");
    }
  };

  const columns = [
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
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: User) => {
        if (record.is_broker_admin) return <Tag>Primary Admin</Tag>;
        return (
          <Space>
            <Button size="small" onClick={() => handleEdit(record)}>
              Edit
            </Button>
            {record.is_active && (
              <Popconfirm title="Deactivate this user?" onConfirm={() => handleDeactivate(record.id)}>
                <Button size="small" danger>
                  Deactivate
                </Button>
              </Popconfirm>
            )}
          </Space>
        );
      },
    },
  ];

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          User Management
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          New User
        </Button>
      </div>

      <Table columns={columns} dataSource={users} rowKey="id" loading={loading} pagination={false} />

      {/* Create modal */}
      <Modal
        title="Create Sub-Admin"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate} initialValues={{ role: "read_only" }}>
          <Form.Item label="Full Name" name="full_name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Email" name="email" rules={[{ required: true, type: "email" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Password" name="password" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item label="Role" name="role" rules={[{ required: true }]}>
            <Select options={ROLES} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              Create
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit modal */}
      <Modal
        title={`Edit ${editingUser?.full_name}`}
        open={!!editingUser}
        onCancel={() => setEditingUser(null)}
        footer={null}
      >
        <Form form={editForm} layout="vertical" onFinish={handleUpdate}>
          <Form.Item label="Full Name" name="full_name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Role" name="role" rules={[{ required: true }]}>
            <Select options={ROLES} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              Save
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
