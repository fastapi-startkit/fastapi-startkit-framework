import JobChat from "../../../components/JobChat"

export default function Index() {
    return <JobChat title="Jobs" endpoint="/jobs/stream" placeholder="Search for jobs..." emptyState="Ask me to find jobs." />
}
