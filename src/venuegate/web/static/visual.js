function renderVisual(target, data) {
    const terminals = new Map();
    for (const row of data.rows) {
        if (!terminals.has(row.zone)) terminals.set(row.zone,[]);
        terminals.get(row.zone).push(row);
    }
    const consoleView = node('div',undefined,'terminal');
    for (const [name, arrivals] of terminals) {
        const peak = Math.max(...arrivals.map(item => item.estimate));
        const staffed = arrivals.filter(item => item.state === '已分派').length;
        const message = node('div');
        message.append(node('strong',`$ ${name}`),document.createTextNode(`  峰值 ${Math.round(peak)} 人 · 增岗 ${staffed} 场`));
        consoleView.append(message);
    }
    target.append(consoleView);
}
