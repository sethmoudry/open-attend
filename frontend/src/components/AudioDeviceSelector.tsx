import React, { useCallback, useEffect, useState } from 'react';

interface AudioDevice {
  deviceId: string;
  label: string;
}

interface AudioDeviceSelectorProps {
  /** Called when user selects a device */
  onDeviceChange?: (deviceId: string) => void;
  /** Additional CSS classes */
  className?: string;
}

export const AudioDeviceSelector: React.FC<AudioDeviceSelectorProps> = ({ onDeviceChange, className = '' }) => {
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');

  const enumerate = useCallback(async () => {
    try {
      // Need at least temporary permission to get device labels
      const tempStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      tempStream.getTracks().forEach((t) => t.stop());

      const allDevices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = allDevices
        .filter((d) => d.kind === 'audioinput')
        .map((d, i) => ({
          deviceId: d.deviceId,
          label: d.label || `Microphone ${i + 1}`,
        }));

      setDevices(audioInputs);

      // Auto-select first if nothing selected
      if (audioInputs.length > 0 && !selectedId) {
        setSelectedId(audioInputs[0].deviceId);
        onDeviceChange?.(audioInputs[0].deviceId);
      }
    } catch {
      // Permission denied or no devices — leave empty
      setDevices([]);
    }
  }, [selectedId, onDeviceChange]);

  // Enumerate on mount
  useEffect(() => {
    enumerate();
  }, [enumerate]);

  // Re-enumerate when devices change (plug/unplug)
  useEffect(() => {
    const handler = () => enumerate();
    navigator.mediaDevices.addEventListener('devicechange', handler);
    return () => navigator.mediaDevices.removeEventListener('devicechange', handler);
  }, [enumerate]);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    setSelectedId(id);
    onDeviceChange?.(id);
  };

  if (devices.length <= 1) {
    // Single device or none — show a simple label
    return (
      <div className={`flex items-center gap-2 text-sm text-gray-400 ${className}`}>
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 14a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3z" />
          <path d="M17 11a1 1 0 10-2 0 3 3 0 11-6 0 1 1 0 10-2 0 5 5 0 005 5v2H9a1 1 0 100 2h6a1 1 0 100-2h-3v-2a5 5 0 005-5z" />
        </svg>
        <span>{devices.length === 1 ? devices[0].label : 'Default Microphone'}</span>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-gray-400" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 14a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3z" />
        <path d="M17 11a1 1 0 10-2 0 3 3 0 11-6 0 1 1 0 10-2 0 5 5 0 005 5v2H9a1 1 0 100 2h6a1 1 0 100-2h-3v-2a5 5 0 005-5z" />
      </svg>
      <select
        value={selectedId}
        onChange={handleChange}
        className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-200 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        {devices.map((d) => (
          <option key={d.deviceId} value={d.deviceId}>
            {d.label}
          </option>
        ))}
      </select>
    </div>
  );
};

export default AudioDeviceSelector;
