import { useTranslation } from 'react-i18next'
import type { CandidateStatus, Community, Gender, SuggestionSource, SuggestionStatus } from '../types'

type Color = 'green' | 'yellow' | 'blue' | 'purple' | 'pink' | 'gray' | 'orange' | 'indigo'

const colorClasses: Record<Color, string> = {
  green:  'bg-green-100 text-green-800',
  yellow: 'bg-yellow-100 text-yellow-800',
  blue:   'bg-blue-100 text-blue-800',
  purple: 'bg-purple-100 text-purple-800',
  pink:   'bg-pink-100 text-pink-800',
  gray:   'bg-gray-100 text-gray-600',
  orange: 'bg-orange-100 text-orange-800',
  indigo: 'bg-indigo-100 text-indigo-800',
}

function Badge({ label, color }: { label: string; color: Color }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colorClasses[color]}`}>
      {label}
    </span>
  )
}

const candidateStatusColor: Record<CandidateStatus, Color> = {
  active:   'green',
  paused:   'yellow',
  engaged:  'purple',
  married:  'blue',
  archived: 'gray',
}

const genderColor: Record<Gender, Color> = {
  male:   'blue',
  female: 'pink',
}

const suggestionStatusColor: Record<SuggestionStatus, Color> = {
  proposed:  'blue',
  reviewing: 'yellow',
  contacted: 'orange',
  met:       'indigo',
  declined:  'gray',
  engaged:   'purple',
}

const suggestionSourceColor: Record<SuggestionSource, Color> = {
  ai:     'indigo',
  manual: 'gray',
}

export const communityKeys: Community[] = [
  'litvish', 'chassidish', 'dati-leumi', 'sephardi', 'mixed',
]

export function CandidateStatusBadge({ status }: { status: CandidateStatus }) {
  const { t } = useTranslation()
  return <Badge label={t(`badges.candidate_status.${status}`)} color={candidateStatusColor[status]} />
}

export function GenderBadge({ gender }: { gender: Gender }) {
  const { t } = useTranslation()
  return <Badge label={t(`badges.gender.${gender}`)} color={genderColor[gender]} />
}

export function CommunityBadge({ community }: { community: Community }) {
  const { t } = useTranslation()
  return <Badge label={t(`badges.community.${community}`)} color="gray" />
}

export function SuggestionStatusBadge({ status }: { status: SuggestionStatus }) {
  const { t } = useTranslation()
  return <Badge label={t(`badges.suggestion_status.${status}`)} color={suggestionStatusColor[status]} />
}

export function SuggestionSourceBadge({ source }: { source: SuggestionSource }) {
  const { t } = useTranslation()
  return <Badge label={t(`badges.suggestion_source.${source}`)} color={suggestionSourceColor[source]} />
}
