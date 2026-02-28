import { useEffect, useState } from "react";
import { Table, Button, Tag, Space, Typography, message, Popconfirm } from "antd";
import { PlusOutlined, EditOutlined, UserAddOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { Broker } from "../../types";
import { getPlatformBrokers, toggleBrokerStatus } from "../../api/endpoints";

export default function BrokerList() {
  const [brokers, setBrokers] = useState<Broker[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchBrokers = async () => {
    setLoading(true);
    try {
      const res = await getPlatformBrokers();
      setBrokers(res.data);
    } catch {
      message.error("Failed to load brokers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBrokers();
  }, []);

  const handleToggleStatus = async (id: number) => {
    try {
      await toggleBrokerStatus(id);
      message.success("Broker status updated");
      fetchBrokers();
    } catch {
      message.error("Failed to update status");
    }
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      render: (name: string, record: Broker) => (
        <a onClick={() => navigate(`/brokers/${record.id}`)}>{name}</a>
      ),
    },
    {
      title: "Slug",
      dataIndex: "slug",
      key: "slug",
      render: (slug: string) => <code>{slug}</code>,
    },
    {
      title: "Contact",
      dataIndex: "contact_email",
      key: "contact_email",
    },
    {
      title: "MT5",
      key: "mt5",
      render: (_: unknown, record: Broker) =>
        record.mt5_configured ? (
          <Tag color="green">Connected</Tag>
        ) : (
          <Tag color="default">Not Configured</Tag>
        ),
    },
    {
      title: "API Key",
      dataIndex: "api_key",
      key: "api_key",
      render: (key: string | null) =>
        key ? <code>{key.slice(0, 8)}...</code> : <Tag color="default">None</Tag>,
    },
    {
      title: "Status",
      key: "status",
      render: (_: unknown, record: Broker) =>
        record.is_active ? (
          <Tag color="green">Active</Tag>
        ) : (
          <Tag color="red">Inactive</Tag>
        ),
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      render: (d: string) => new Date(d).toLocaleDateString(),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: Broker) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => navigate(`/brokers/${record.id}`)}
          >
            Edit
          </Button>
          <Button
            size="small"
            icon={<UserAddOutlined />}
            onClick={() => navigate(`/brokers/${record.id}`, { state: { tab: "admins" } })}
          >
            Admins
          </Button>
          <Popconfirm
            title={`${record.is_active ? "Deactivate" : "Activate"} this broker?`}
            onConfirm={() => handleToggleStatus(record.id)}
          >
            <Button size="small" danger={record.is_active}>
              {record.is_active ? "Deactivate" : "Activate"}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Brokers
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/brokers/new")}>
          New Broker
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={brokers}
        rowKey="id"
        loading={loading}
        pagination={false}
      />
    </>
  );
}
