Sync scaffold files จาก hub ไปยัง registered projects

## วิธีใช้

```
/sync-agents                          # sync ทุก active project (agents + commands + scripts)
/sync-agents bay-voc                  # sync เฉพาะ project นี้
/sync-agents --dry-run                # ดูว่าจะเปลี่ยนอะไร ไม่แตะไฟล์จริง
/sync-agents --force                  # overwrite ไฟล์ที่ถูกแก้ใน project
/sync-agents --only agents            # sync เฉพาะ agents/*.md + .claude/agents/*.md
/sync-agents --only commands          # sync เฉพาะ .claude/commands/*.md
/sync-agents --only scripts           # sync เฉพาะ scripts/*.py
```

## ขั้นตอน

**1. รัน sync script:**
```bash
python sync_agents.py $ARGUMENTS
```

**2. แสดงผลลัพธ์:**
- `+` = ไฟล์ใหม่ที่เพิ่มไปใน project
- `↑` = ไฟล์ที่อัปเดตจาก scaffold
- `~` = ไฟล์ที่ข้ามเพราะแตกต่างจาก scaffold (ต้องใช้ --force)
- `✗` = error (เช่น project path ไม่พบ)

**3. ถ้ามี skipped files** — แจ้ง user ว่าไฟล์ไหนถูกแก้ใน project และถามว่าต้องการ overwrite ไหม

## ไฟล์ที่ sync (Group A)
- `agents/` — system prompts ที่ใช้โดย orchestrator.py
- `.claude/agents/` — Claude Code subagents
- `.claude/commands/` — slash commands
- `scripts/` — Python pipeline scripts (ยกเว้น init_project.py)

## ไฟล์ที่ไม่ sync (project-specific)
- `CLAUDE.md` — มี BASE_URL, project name
- `playwright.config.ts` — มี config เฉพาะ project
- `tests/` — อาจมี customization
- `templates/` — อาจมีการแก้ template เฉพาะ project
