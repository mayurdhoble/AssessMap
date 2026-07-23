const colorMap = {
  orange: 'text-orange-600 bg-orange-50',
  purple: 'text-purple-600 bg-purple-50',
  blue: 'text-blue-600 bg-blue-50',
  green: 'text-green-600 bg-green-50',
  teal: 'text-teal-600 bg-teal-50',
  indigo: 'text-indigo-600 bg-indigo-50',
}

export default function KPICard({ title, value, subtitle, color = 'orange', icon: Icon }) {
  const cls = colorMap[color] || colorMap.orange
  const [textColor, bgColor] = cls.split(' ')

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{title}</p>
        {Icon && (
          <span className={`w-8 h-8 rounded-lg flex items-center justify-center ${bgColor}`}>
            <Icon size={16} className={textColor} />
          </span>
        )}
      </div>
      <p className={`text-3xl font-bold ${textColor}`}>{value ?? '—'}</p>
      {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
    </div>
  )
}
