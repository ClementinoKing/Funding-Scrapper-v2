import { useMemo, useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  ArrowLeft,
  ExternalLink,
  Calendar,
  DollarSign,
  Building2,
  FileText,
  Bookmark,
  BookmarkCheck,
  Copy,
  CheckCircle2,
  Sparkles,
} from 'lucide-react'
import { 
  getBusinessMatch
} from '@/lib/triggerMatching';
import { useProfile } from '@/hooks/use-profile'
import { UserProfileView } from '@/types/api'
import {CircularProgress} from "@/components/shared/circular-progress"

export default function FundingDetail() {
  const { programId } = useParams()
  const navigate = useNavigate()

  const { data: profile } = useProfile();
  const userProfile = profile?.[0] as UserProfileView;

  const [program, setProgram] = useState<unknown>(null)
  const [isFetching, setIsFetching] = useState(true);
  const [copied, setCopied] = useState(false)
  const [isSaved, setIsSaved] = useState(false)
  const [isSaving, setIsSaving] = useState(false);
  const error = ''

  const loadMatch = async () => {
    if (!userProfile?.business_id) return;

    setIsFetching(true)
    const matchResult = await getBusinessMatch(userProfile?.business_id, programId as string);
    if (matchResult.data) {
      setProgram(matchResult.data);
      console.log("Loaded match:", matchResult.data);
    }
    setIsFetching(false)
  }

  useEffect(() => {
      if(userProfile?.business_id) {
        (async () => loadMatch())();
      }
    }, [userProfile]);

  function copyLink() {
    navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }


  // Handle save/unsave
  async function handleSaveToggle() {
    if (!program?.program_id) return;

    setIsSaving(true);
    setIsSaving(false);
  }

  const siblingPrograms = useMemo(() => {
    return []
  }, [])

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 flex items-center justify-center px-4">
        <Card className="max-w-md w-full border-red-200 dark:border-red-900">
          <CardContent className="p-6 text-center">
            <p className="text-red-600 dark:text-red-400 font-medium">{error}</p>
            <Button className="mt-4" onClick={() => navigate('/dashboard')}>
              Go to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!program && !isFetching) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 flex items-center justify-center px-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center">
            <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <h2 className="text-lg font-semibold mb-2">Program not found</h2>
            <p className="text-sm text-muted-foreground mb-4">
              The requested funding opportunity could not be located.
            </p>
            <div className="flex gap-2 justify-center">
              <Button variant="outline" onClick={() => navigate(-1)}>
                <ArrowLeft className="w-4 h-4 mr-2" /> Back
              </Button>
              <Button onClick={() => navigate('/dashboard')}>
                Go to Dashboard
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <div className="mx-auto sm:px-4 lg:px-0 py-8">
        {/* Navigation Bar */}
        <div className="mb-8 flex items-center justify-between">
          <Button 
            variant="ghost" 
            onClick={() => navigate('/app/matches')}
            className="gap-2 -ml-2"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </Button>
          <div className="flex items-center gap-2">
            <Button 
              variant="ghost" 
              size="sm"
              onClick={copyLink}
              className="gap-2"
            >
              {copied ? (
                <>
                  <CheckCircle2 className="w-4 h-4" /> Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" /> Copy
                </>
              )}
            </Button>
            <Button 
              variant="ghost" 
              size="sm" 
              className="gap-2"
              onClick={handleSaveToggle}
              disabled={isSaving || !program?.program_id}
            >
              {isSaved ? (
                <>
                  <BookmarkCheck className="w-4 h-4" />
                </>
              ) : (
                <>
                  <Bookmark className="w-4 h-4" />
                </>
              )}
            </Button>
            {program?.program_url && (
              <a href={program?.program_url} target="_blank" rel="noreferrer">
                <Button size="sm" className="gap-2">
                  <ExternalLink className="w-4 h-4" /> Apply
                </Button>
              </a>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Hero Section */}
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-green-500 flex items-center justify-center shadow-lg">
                      <Building2 className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">{program?.program_source}</p>
                      {!program ? (
                        <Skeleton className="h-5 w-24 mt-1" />
                      ) : (
                        (
                          <div className="flex items-center gap-2 mt-1">
                            <Badge 
                              variant={(program?.final_score || 0) >= 50 ? "default" : "secondary"}
                              className="gap-1.5 text-xs"
                            >
                              <Sparkles className="w-3 h-3" />
                              {(program?.final_score || 0)}% Match
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              Active
                            </Badge>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                  <div className="flex gap-4 items-center">
                    <h1 className="text-4xl font-bold tracking-tight leading-tight">
                      {program?.program_name || 'Untitled program'}
                    </h1>
                    <Button variant="outline" size="sm" className="gap-2" onClick={() => navigate(`/app/programs/${program?.program_id}`)}>
                      <ExternalLink className="w-4 h-4" /> View Program
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            {/* Content Sections */}
            <Card className="shadow-sm">
              <CardContent className="p-6 space-y-8">
                {/* Overview */}
                {/* <section className="space-y-3">
                  <div className="flex items-center gap-2 pb-2">
                    <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                      <FileText className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                    </div>
                    <h2 className="text-xl font-semibold">Overview</h2>
                  </div>
                  <div className="pl-10">
                    <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap text-justify">
                      {program?.program_funding_lines || 'No summary available.'}
                    </p>
                  </div>
                </section> */}

                <Separator className="my-8" />

                {/* Eligibility */}
                <section className="space-y-3">
                  <div className="flex items-center gap-2 pb-2">
                    <div className="w-8 h-8 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                      <Building2 className="w-4 h-4 text-green-600 dark:text-green-400" />
                    </div>
                    <h2 className="text-xl font-semibold">Eligibility Criteria</h2>
                  </div>
                  <div className="pl-10">
                    <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap text-justify">
                      {program?.program_eligibility || 'Not specified.'}
                    </p>
                  </div>
                </section>

                {/* Funding Amount */}
                {program?.program_funding_amount_max && (
                  <>
                    <Separator className="my-8" />
                    <section className="space-y-3">
                      <div className="flex items-center gap-2 pb-2">
                        <div className="w-8 h-8 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                          <DollarSign className="w-4 h-4 text-green-600 dark:text-green-400" />
                        </div>
                        <h2 className="text-xl font-semibold">Funding Amount</h2>
                      </div>
                      <div className="pl-10 text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap text-justify">
                        From {program?.program_funding_amount_min?.toLocaleString() ?? "0.00"} <span className="font-semibold">{program?.program_funding_currency}</span>{" "}
                        to {program?.program_funding_currency} {program?.program_funding_amount_max?.toLocaleString()} <span className="font-semibold">{program?.program_funding_currency}</span> 
                      </div>
                    </section>
                  </>
                )}

                {/* Deadline */}
                {program?.program_deadline_date && (
                  <>
                    <Separator className="my-8" />
                    <section className="space-y-3">
                      <div className="flex items-center gap-2 pb-2">
                        <div className="w-8 h-8 rounded-lg bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
                          <Calendar className="w-4 h-4 text-orange-600 dark:text-orange-400" />
                        </div>
                        <h2 className="text-xl font-semibold">Deadline</h2>
                      </div>
                      <div className="pl-10">
                        <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap text-justify">
                          {program?.program_deadline_date}
                        </p>
                      </div>
                    </section>
                  </>
                )}

                {/* Source */}
                {program?.program_url && (
                  <>
                    <Separator className="my-8" />
                    <section className="space-y-3">
                      <h2 className="text-lg font-semibold">Source</h2>
                      <div className="pl-0 flex items-center gap-3 flex-wrap">
                        <Badge variant="secondary" className="text-sm py-2 px-4 font-mono">
                          {program?.program_url.replace(/^https?:\/\//, '')}
                        </Badge>
                        <a href={program?.program_url} target="_blank" rel="noreferrer">
                          <Button variant="outline" size="sm" className="gap-2">
                            <ExternalLink className="w-4 h-4" /> View Source
                          </Button>
                        </a>
                      </div>
                    </section>
                  </>
                )}

                {/* Subp>rograms */}
                
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1 space-y-6">
            {!program ? (
              <Card className="shadow-sm">
                <CardHeader className="pb-4">
                  <Skeleton className="h-6 w-32 mb-2" />
                  <Skeleton className="h-4 w-48" />
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex justify-center">
                    <Skeleton className="h-40 w-40 rounded-full" />
                  </div>
                  <div className="space-y-3">
                    {[...Array(3)].map((_, i) => (
                      <div key={i} className="flex items-center justify-between p-2">
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-4 w-16" />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="shadow-sm sticky top-8">
                <CardHeader className="pb-4">
                  <CardTitle className="text-lg font-semibold">Match Score</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    How well this program matches your profile
                  </p>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Circular Progress */}
                  <div className="flex justify-center py-2">
                    <CircularProgress 
                      value={(program.final_score || 0)} 
                      size={100}
                      strokeWidth={10}
                    />
                  </div>

                  <div className="text-sm text-muted-foreground whitespace-pre-wrap text-justify">
                    {program.ai_analysis}
                  </div>

                  {/* Score Breakdown */}
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold mb-3 text-foreground">Score Breakdown</h3>
                    {program?.match_reasons && program?.match_reasons?.length > 0 ? (
                      (() => <div className="space-y-1.5">
                            {program.match_reasons.map((item, index) => {
                              return (
                                <div 
                                  key={index}
                                  className="flex items-center justify-between p-2.5 rounded-lg hover:bg-accent/50 transition-colors border border-transparent hover:border-border"
                                >
                                  <div className="flex items-center gap-2.5 flex-1 min-w-0">
                                    <span className="w-6 h-6 text-xs text-green-600 dark:text-green-400 flex-shrink-0 border-2 border-green-600 rounded-full flex justify-center items-center">
                                      {item.score}
                                    </span>
                                    <span className="text-xs md:text-sm text-foreground font-medium">
                                      {item.reason}
                                    </span>
                                  </div>
                                </div>
                              )
                            })}
                          </div>)()
                    ) : (
                      <p className="text-sm text-muted-foreground text-center py-6">
                        No breakdown available
                      </p>
                    )}
                  </div>

                  {/* Eligibility Gaps */}
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold mb-3 text-foreground">Eligibility Gaps</h3>
                    {program?.eligibility_gaps && program?.eligibility_gaps?.length > 0 ? (
                      (() => <div className="space-y-1.5">
                            {program.eligibility_gaps.map((item, index) => {
                              return (
                                <div 
                                  key={index}
                                  className="flex items-center justify-between p-2.5 rounded-lg hover:bg-accent/50 transition-colors border border-transparent hover:border-border"
                                >
                                  <div className="flex items-center gap-2.5 flex-1 min-w-0">
                                    <span className="w-6 h-6 text-xs text-red-600 dark:text-red-400 flex-shrink-0 border-2 border-red-600 rounded-full flex justify-center items-center">
                                      {item.score}
                                    </span>
                                    <span className="text-xs md:text-sm text-foreground font-medium">
                                      {item.reason}
                                    </span>
                                  </div>
                                </div>
                              )
                            })}
                          </div>)()
                    ) : (
                      <p className="text-sm text-muted-foreground text-center py-6">
                        No breakdown available
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Related Programs */}
            {!program ? (
              <Card className="shadow-sm">
                <CardHeader className="pb-4">
                  <Skeleton className="h-6 w-40 mb-2" />
                  <Skeleton className="h-4 w-56" />
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {[...Array(3)].map((_, i) => (
                      <div key={i} className="p-3 rounded-lg border">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0 space-y-2">
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-3 w-3/4" />
                          </div>
                          <Skeleton className="h-5 w-12 flex-shrink-0" />
                        </div>
                      </div>
                    ))}
                  </div>
                  <Skeleton className="h-10 w-full mt-4" />
                </CardContent>
              </Card>
            ) : siblingPrograms?.length > 0 ? (
              <Card className="shadow-sm">
                <CardHeader className="pb-4">
                  <CardTitle className="text-lg font-semibold">Related Programs</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    Matched programs from the same organization
                  </p>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-1.5">
                    {siblingPrograms?.map((p, i) => (
                      <li key={`sib-${i}`}>
                        <Link
                          className="block p-3 rounded-lg hover:bg-accent transition-colors group border border-transparent hover:border-border"
                          to={`/app/programs/${p.program_id}`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium group-hover:text-primary transition-colors line-clamp-2 leading-snug">
                                {p.name || 'Untitled program'}
                              </p>
                              {p.fundingAmount && (
                                <p className="text-xs text-muted-foreground mt-1.5 line-clamp-1">
                                  {p.fundingAmount}
                                </p>
                              )}
                            </div>
                            {p.matchScore !== undefined && (
                              <Badge variant="outline" className="flex-shrink-0 gap-1 ml-2">
                                <Sparkles className="w-3 h-3" />
                                {p.matchScore}%
                              </Badge>
                            )}
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <Button 
                    variant="outline" 
                    className="w-full mt-4" 
                    onClick={() => navigate('/app/programs')}
                  >
                    View All Programs
                  </Button>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}


