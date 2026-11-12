"""Create manuscript tables and plot data from recomputed numerical results."""
from common import OUTPUT,read,save

def main():
    """Export exact numerical sources and concise Markdown presentation tables."""
    analysis=read(OUTPUT/'analysis.json');diagnostics=read(OUTPUT/'diagnostics.json')
    models=['GPT','Claude','DeepSeek'];tasks=['tot2023','genomics2007','tar2018_full']
    conditions=['S0','S1','S2','S3','S4'];means=analysis['means']
    lines=['# Tables for the three-model paper','','All values use the matched 3,240-cell cohort.','',
        '## Official mean scores','','| Task | Model | S0 | S1 | S2 | S3 | S4 |','|---|---|---:|---:|---:|---:|---:|']
    for task in tasks:
        for model in models:
            values=[means[f'{model}/{task}/{c}']['primary_score']['mean'] for c in conditions]
            lines.append('| '+task+' | '+model+' | '+' | '.join(f'{x:.4f}' for x in values)+' |')
    lines+=['','## Paired changes from S0','','| Model | Task | Condition | Change | 95% interval | Adjusted p | Wins / ties / losses |',
        '|---|---|---|---:|---|---:|---|']
    effects=[]
    for model in models:
        for task in tasks:
            for c in conditions[1:]:
                value=analysis['contrasts'][f'{model}/{task}/{c}']['primary'];lo,hi=value['paired_bootstrap_95_interval']
                effects.append({'model':model,'task':task,'condition':c,**value})
                lines.append(f'| {model} | {task} | {c} | {value["mean_difference"]:+.4f} | [{lo:+.4f}, {hi:+.4f}] | {value["holm_p"]:.4f} | {value["wins"]} / {value["ties"]} / {value["losses"]} |')
    lines+=['','## TAR acquisition and final selection','','| Model | Condition | Relevant pool | Final exact recall | Gap |',
        '|---|---|---:|---:|---:|']
    coverage=[]
    for model in models:
        for c in conditions:
            value=diagnostics['tar'][f'{model}/{c}'];coverage.append({'model':model,'condition':c,**value})
            lines.append(f'| {model} | {c} | {value["pool_coverage"]:.4f} | {value["selected_exact"]:.4f} | {value["gap"]:.4f} |')
    baseline=read(OUTPUT/'official_baselines.json');fixed=[]
    lines+=['','## Fixed retrieval baselines','','| Task | BM25 | BM25+RM3 |','|---|---:|---:|']
    for task in tasks:
        values={c:sum(r['primary_score'] for r in baseline if r['task']==task and r['condition']==c)/sum(r['task']==task and r['condition']==c for r in baseline) for c in ['B0','B1']}
        fixed.append({'task':task,**values});lines.append(f'| {task} | {values["B0"]:.4f} | {values["B1"]:.4f} |')
    (OUTPUT/'paper_tables.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save('paper_plot_data.json',{'skill_effects':effects,'tar_coverage':coverage,'fixed_baselines':fixed})

if __name__=='__main__':main()
