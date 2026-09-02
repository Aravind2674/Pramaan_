import { TimelineChart } from '../../components/timeline/TimelineChart'
import { KindBadge } from '../../components/ui/Badge'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { EmptyState, ErrorBanner, Spinner } from '../../components/ui/Feedback'
import { useTimeline } from '../../hooks/queries'
import { useCaseId } from '../../hooks/useCaseId'

const LEGEND_KINDS = ['recorded', 'recovered', 'corrupt', 'unknown']

export function TimelineTab() {
  const caseId = useCaseId()
  const timelineQuery = useTimeline(caseId)

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader
          title="Multi-channel timeline"
          subtitle="Every clip with a known start and end time, composed across channels."
          action={
            <div className="flex gap-3">
              {LEGEND_KINDS.map((kind) => (
                <KindBadge key={kind} kind={kind} />
              ))}
            </div>
          }
        />
        <CardBody>
          {timelineQuery.isPending && <Spinner label="Loading timeline…" />}
          {timelineQuery.isError && <ErrorBanner error={timelineQuery.error} />}
          {timelineQuery.isSuccess && timelineQuery.data.segments.length === 0 && (
            <EmptyState>
              No clips have a known time range yet -- set one from the Clips tab to see them here.
            </EmptyState>
          )}
          {timelineQuery.isSuccess && timelineQuery.data.segments.length > 0 && (
            <TimelineChart segments={timelineQuery.data.segments} />
          )}
        </CardBody>
      </Card>
    </div>
  )
}
