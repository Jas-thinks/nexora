import json, re, concurrent.futures as cf
import httpx
UA={"User-Agent":"NexoraCPMentor/0.1 (research probe; respects robots)"}
SRC={
"codeforces":["https://codeforces.com/problemset","https://codeforces.com/api/problemset.problems","https://codeforces.com/api/contest.list?gym=true"],
"codechef":["https://www.codechef.com/practice","https://www.codechef.com/api/list/contests/all","https://www.codechef.com/api/list/problems/easy"],
"leetcode":["https://leetcode.com/problemset/","https://leetcode.com/api/problems/algorithms/"],
"atcoder":["https://atcoder.jp/contests/archive","https://kenkoooo.com/atcoder/resources/merged-problems.json","https://kenkoooo.com/atcoder/resources/problems.json"],
"geeksforgeeks":["https://www.geeksforgeeks.org/explore","https://www.geeksforgeeks.org/problems/"],
"hackerrank":["https://www.hackerrank.com/domains/algorithms","https://www.hackerrank.com/rest/contests/master/tracks/algorithms/challenges?offset=0&limit=5"],
"hackerearth":["https://www.hackerearth.com/practice/","https://www.hackerearth.com/challenges/"],
"topcoder":["https://www.topcoder.com/challenges","https://api.topcoder.com/v5/challenges?perPage=2"],
"codesignal":["https://app.codesignal.com/arcade","https://codesignal.com/"],
"cses":["https://cses.fi/problemset/","https://cses.fi/problemset/list/"],
"spoj":["https://www.spoj.com/problems/classical/","https://www.spoj.com/problems/"],
"kattis":["https://open.kattis.com/problems","https://open.kattis.com/contests"],
"dmoj":["https://dmoj.ca/problems/","https://dmoj.ca/api/v2/problems?page=1","https://dmoj.ca/api/v2/problem/aplusb"],
"timus":["https://acm.timus.ru/problemset.aspx"],
"projecteuler":["https://projecteuler.net/archives","https://projecteuler.net/recent","https://projecteuler.net/minimal=problems"],
"toph":["https://toph.co/problems","https://toph.co/contests"],
"csacademy":["https://csacademy.com/"],
"uva":["https://onlinejudge.org/index.php?option=com_onlinejudge&Itemid=8"],
"lightoj":["https://lightoj.com/problems"],
"usaco":["https://usaco.org/","https://usaco.org/index.php?page=contests"],
"aizu":["https://onlinejudge.u-aizu.ac.jp/problems","https://judgeapi.u-aizu.ac.jp/resources/problems?page=0&size=3"],
"yukicoder":["https://yukicoder.me/","https://yukicoder.me/api/v1/problems"],
"luogu":["https://www.luogu.com.cn/problem/list","https://www.luogu.com.cn/problem/list?_contentOnly=1"],
"omegaup":["https://omegaup.com/arena/","https://omegaup.com/api/problem/list/?page=1&rowcount=3"],
"beecrowd":["https://judge.beecrowd.com/en/problems/index/1"],
"tlx":["https://tlx.toki.id/problems","https://api.tlx.toki.id/v2/problems/public?page=1"],
"quera":["https://quera.org/problemset"],
"eolymp":["https://eolymp.com/en/problems","https://api.eolymp.com/spec"],
"france-ioi":["https://www.france-ioi.org/"],
"kilonova":["https://kilonova.ro/","https://kilonova.ro/api/problem/search"],
"szkopul":["https://szkopul.edu.pl/"],
"infoarena":["https://infoarena.ro/"],
"neps":["https://neps.academy/"],
"ksp":["https://ksp.mff.cuni.cz/"],
"codeup":["https://codeup.kr/"],
"mendo":["https://mendo.mk/"],
"icpc":["https://icpc.global/","https://u.icpc.global/problems/","https://u.icpc.global/training/","https://u.icpc.global/training/online-judging-systems/"],
"ubc":["https://icpc.cs.ubc.ca/resources"],
"clist":["https://clist.by/","https://clist.by/api/v4/contest/"],
"cf-gym":["https://codeforces.com/gyms"],
"google-cc":["https://codingcompetitions.withgoogle.com/"],
"rosalind":["https://rosalind.info/problems/locations/"],
"usaco-guide":["https://usaco.guide/","https://usaco.guide/general/contests"],
"kactl":["https://github.com/kth-competitive-programming/kactl","https://api.github.com/repos/kth-competitive-programming/kactl/license"],
"cp-algorithms":["https://cp-algorithms.com/"],
"cses-book":["https://cses.fi/book/book.pdf"],
"a2oj":["https://a2oj.netlify.app/"],
"450dsa":["https://450dsa.com/"],
"tuf":["https://takeuforward.org/"],
"neetcode":["https://neetcode.io/practice"],
"grind75":["https://www.techinterviewhandbook.org/grind75"],
}
def robots(host):
    try:
        r=httpx.get(f"https://{host}/robots.txt",headers=UA,timeout=12,follow_redirects=True)
        if r.status_code!=200 or "html" in r.headers.get("content-type","") and "<html" in r.text[:200].lower(): return {"robots":r.status_code,"note":"none/HTML"}
        t=r.text; ua_all=False; dis=[]
        for line in t.splitlines():
            l=line.strip()
            if l.lower().startswith("user-agent:"): ua_all = l.split(":",1)[1].strip()=="*"
            elif ua_all and l.lower().startswith("disallow:") and l.split(":",1)[1].strip(): dis.append(l.split(":",1)[1].strip())
        sig=re.findall(r"Content-Signal:.*",t)[:1]
        return {"robots":200,"disallow":dis[:12],"content_signal":sig,"ai_restrictions":bool(re.search(r"ai-train\s*=\s*no|GPTBot|ClaudeBot",t,re.I))}
    except Exception as e: return {"robots":"err","note":type(e).__name__}
def hit(u):
    try:
        r=httpx.get(u,headers=UA,timeout=20,follow_redirects=True)
        ct=r.headers.get("content-type","").split(";")[0]
        j=None
        if "json" in ct:
            try: d=r.json(); j=type(d).__name__+(f"[{len(d)}]" if hasattr(d,"__len__") else "")
            except Exception: pass
        return {"url":u,"status":r.status_code,"ct":ct,"bytes":len(r.content),"final":str(r.url) if str(r.url)!=u else None,"json":j}
    except Exception as e: return {"url":u,"status":"ERR","err":type(e).__name__}
out={}
hosts={}
for k,us in SRC.items():
    for u in us: hosts.setdefault(re.sub(r"https?://([^/]+)/?.*",r"\1",u),None)
with cf.ThreadPoolExecutor(8) as ex:
    rb={h:f for h,f in ((h,ex.submit(robots,h)) for h in hosts)}
    res={(k,u):ex.submit(hit,u) for k,us in SRC.items() for u in us}
    for (k,u),f in res.items(): out.setdefault(k,{"hits":[],"robots":{}})["hits"].append(f.result())
    for k,us in SRC.items():
        for u in us:
            h=re.sub(r"https?://([^/]+)/?.*",r"\1",u); out[k]["robots"][h]=rb[h].result()
json.dump(out,open("probe.json","w"),indent=1)
for k,v in out.items():
    print(f"\n[{k}]")
    for h in v["hits"]: print(f"  {h['status']!s:>4} {h.get('ct','') or h.get('err',''):<22} {h.get('bytes',''):>8} {h.get('json') or ''} {h['url'][:80]}{'  -> '+h['final'][:50] if h.get('final') else ''}")
    for host,r in v["robots"].items(): print(f"  robots[{host}]: {r}")
