import React, { useState } from 'react';
import {
  Modal,
  FormItem,
  Input,
  Button,
  Alert,
  Select
} from '../ui';
import { useCreateService } from '../../hooks/useApi';

interface AddServiceModalProps {
  visible: boolean;
  onCancel: () => void;
}

interface FormData {
  name: string;
  description: string;
  transport: 'http' | 'stdio';
  endpoint?: string;
  command?: string;
  authStrategy: string;
}

export const AddServiceModal: React.FC<AddServiceModalProps> = ({
  visible,
  onCancel
}) => {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    transport: 'http',
    endpoint: '',
    command: '',
    authStrategy: 'no_auth'
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  
  const createService = useCreateService();

  const handleInputChange = (field: keyof FormData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setResult(null);
    
    try {
      const serviceData = {
        name: formData.name,
        description: formData.description,
        transport: formData.transport,
        enabled: true,
        auth: {
          strategy: formData.authStrategy
        },
        ...(formData.transport === 'http' 
          ? { 
              endpoint: formData.endpoint || '',
              timeout: 5000,
              health_check_path: '/health'
            }
          : { 
              command: formData.command || '',
              working_directory: '/tmp'
            }
        ),
        tags: []
      };

      await createService.mutateAsync(serviceData as any);
      setResult({ type: 'success', message: 'Service created successfully!' });
      
      // Reset form after successful creation
      setTimeout(() => {
        setFormData({
          name: '',
          description: '',
          transport: 'http',
          endpoint: '',
          command: '',
          authStrategy: 'no_auth'
        });
        setResult(null);
        onCancel();
      }, 1500);
      
    } catch (error: any) {
      setResult({ 
        type: 'error', 
        message: error?.message || 'Failed to create service. Please try again.' 
      });
    } finally {
      setLoading(false);
    }
  };

  const isValid = formData.name.trim() && 
    (formData.transport === 'http' ? formData.endpoint?.trim() : formData.command?.trim());

  return (
    <Modal
      title="Add New MCP Service"
      open={visible}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          Cancel
        </Button>,
        <Button 
          key="submit" 
          type="primary" 
          loading={loading}
          disabled={!isValid}
          onClick={handleSubmit}
        >
          Create Service
        </Button>
      ]}
      width={600}
      destroyOnClose
    >
      <div className="space-y-4">
        <FormItem label="Service Name" required>
          <Input
            placeholder="Enter service name"
            value={formData.name}
            onChange={(value) => handleInputChange('name', value)}
          />
        </FormItem>

        <FormItem label="Description">
          <Input
            placeholder="Enter service description"
            value={formData.description}
            onChange={(value) => handleInputChange('description', value)}
          />
        </FormItem>

        <FormItem label="Transport Type" required>
          <Select
            value={formData.transport}
            onChange={(value) => handleInputChange('transport', value as string)}
            options={[
              { label: 'HTTP', value: 'http' },
              { label: 'STDIO', value: 'stdio' }
            ]}
          />
        </FormItem>

        {formData.transport === 'http' && (
          <FormItem label="Endpoint URL" required>
            <Input
              placeholder="http://localhost:8000"
              value={formData.endpoint}
              onChange={(value) => handleInputChange('endpoint', value)}
            />
          </FormItem>
        )}

        {formData.transport === 'stdio' && (
          <FormItem label="Command" required>
            <Input
              placeholder="python /path/to/server.py"
              value={formData.command}
              onChange={(value) => handleInputChange('command', value)}
            />
          </FormItem>
        )}

        <FormItem label="Authentication Strategy">
          <Select
            value={formData.authStrategy}
            onChange={(value) => handleInputChange('authStrategy', value as string)}
            options={[
              { label: 'No Authentication', value: 'no_auth' },
              { label: 'Passthrough', value: 'passthrough' },
              { label: 'OBO Required', value: 'obo_required' }
            ]}
          />
        </FormItem>

        {result && (
          <Alert
            type={result.type}
            message={result.message}
            showIcon
          />
        )}
      </div>
    </Modal>
  );
};
