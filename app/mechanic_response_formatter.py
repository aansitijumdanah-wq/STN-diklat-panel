"""
Response formatter untuk mechanic-focused answers
Memastikan AI responses structured dan professional untuk bengkel use case
"""

from typing import Dict, List, Optional


class MechanicResponseFormatter:
    """Format AI responses untuk bengkel mekanik dengan struktur yang jelas"""
    
    @staticmethod
    def format_diagnosis(
        symptom: str,
        causes: List[Dict],
        next_steps: str = None,
        estimated_time: str = None,
        tools_needed: List[str] = None,
        safety_warning: str = None,
        source: str = None
    ) -> str:
        """
        Format diagnosis response dengan struktur yang jelas
        
        Args:
            symptom: Deskripsi gejala/masalah
            causes: List [{name, probability, check_steps, notes}]
            next_steps: Langkah selanjutnya
            estimated_time: Perkiraan waktu diagnosis
            tools_needed: Tools yang diperlukan
            safety_warning: Peringatan keselamatan
            source: Sumber dokumen
        
        Returns:
            Formatted diagnosis string
        """
        output = []
        
        # IDENTIFIKASI
        output.append("🔍 **GEJALA/MASALAH**:")
        output.append(f"   {symptom}\n")
        
        # ANALISIS - Kemungkinan Penyebab
        if causes:
            output.append("🔧 **KEMUNGKINAN PENYEBAB** (urut by likelihood):")
            for i, cause in enumerate(causes, 1):
                prob = cause.get('probability', '?')
                name = cause.get('name', 'Unknown')
                output.append(f"\n   {i}. **{name}** ({prob}% probability)")
                
                check_steps = cause.get('check_steps', '')
                if check_steps:
                    output.append(f"      └─ Cara check: {check_steps}")
                
                notes = cause.get('notes', '')
                if notes:
                    output.append(f"      └─ Notes: {notes}")
        
        # LANGKAH SELANJUTNYA
        if next_steps:
            output.append("\n\n🛠️ **LANGKAH SELANJUTNYA**:")
            output.append(f"   {next_steps}")
        
        # CATATAN PRAKTIS
        notes_section = []
        if estimated_time:
            notes_section.append(f"⏱️  Waktu: {estimated_time}")
        if tools_needed:
            tools_str = ", ".join(tools_needed) if isinstance(tools_needed, list) else tools_needed
            notes_section.append(f"🛠️  Tools: {tools_str}")
        if safety_warning:
            notes_section.append(f"⚠️  **SAFETY**: {safety_warning}")
        if source:
            notes_section.append(f"📖 Source: {source}")
        
        if notes_section:
            output.append("\n\n**CATATAN PENTING**:")
            for note in notes_section:
                output.append(f"   • {note}")
        
        return "\n".join(output)
    
    @staticmethod
    def format_procedure(
        title: str,
        steps: List[Dict],
        estimated_time: str = None,
        tools_needed: List[str] = None,
        parts_needed: List[str] = None,
        oem_part_number: str = None,
        safety_warnings: List[str] = None,
        tips: List[str] = None,
        source: str = None
    ) -> str:
        """
        Format prosedur perbaikan dengan langkah-langkah jelas
        
        Args:
            title: Judul prosedur
            steps: List [{description, details, torque, caution}]
            estimated_time: Perkiraan waktu kerja
            tools_needed: Alat yang diperlukan
            parts_needed: Suku cadang yang diperlukan
            oem_part_number: Nomor part OEM jika ada
            safety_warnings: Daftar peringatan keselamatan
            tips: Tips praktis
            source: Sumber dokumen
        
        Returns:
            Formatted procedure string
        """
        output = []
        
        # JUDUL
        output.append(f"**{title}**\n")
        
        # QUICK INFO
        quick_info = []
        if estimated_time:
            quick_info.append(f"⏱️  Waktu: {estimated_time}")
        if tools_needed:
            tools_str = ", ".join(tools_needed) if isinstance(tools_needed, list) else tools_needed
            quick_info.append(f"🛠️  Tools: {tools_str}")
        if parts_needed:
            parts_str = ", ".join(parts_needed) if isinstance(parts_needed, list) else parts_needed
            quick_info.append(f"🔧 Parts: {parts_str}")
        if oem_part_number:
            quick_info.append(f"📍 OEM Part: {oem_part_number}")
        
        if quick_info:
            output.extend(quick_info)
            output.append("")
        
        # LANGKAH-LANGKAH
        if steps:
            output.append("**LANGKAH-LANGKAH**:")
            for i, step in enumerate(steps, 1):
                output.append(f"\n**Step {i}: {step.get('title', 'Step ' + str(i))}**")
                
                desc = step.get('description', '')
                if desc:
                    output.append(f"   {desc}")
                
                details = step.get('details', [])
                if details:
                    for detail in (details if isinstance(details, list) else [details]):
                        output.append(f"   • {detail}")
                
                torque = step.get('torque', '')
                if torque:
                    output.append(f"   • Torque: {torque}")
                
                caution = step.get('caution', '')
                if caution:
                    output.append(f"   • ⚠️ {caution}")
        
        # PERINGATAN KESELAMATAN
        if safety_warnings:
            output.append("\n\n**⚠️ PERINGATAN KESELAMATAN**:")
            for warning in safety_warnings:
                output.append(f"   • {warning}")
        
        # TIPS PRAKTIS
        if tips:
            output.append("\n\n**💡 TIPS PRAKTIS**:")
            for tip in tips:
                output.append(f"   • {tip}")
        
        # SOURCE
        if source:
            output.append(f"\n📖 Source: {source}")
        
        return "\n".join(output)
    
    @staticmethod
    def format_maintenance_schedule(
        vehicle_type: str,
        schedules: List[Dict],
        notes: str = None,
        source: str = None
    ) -> str:
        """
        Format maintenance schedule dengan interval yang jelas
        
        Args:
            vehicle_type: Jenis kendaraan (e.g., Daihatsu Avanza)
            schedules: List [{interval, km_or_time, items}]
            notes: Catatan tambahan
            source: Sumber dokumen
        
        Returns:
            Formatted schedule string
        """
        output = []
        
        output.append(f"**Jadwal Perawatan: {vehicle_type}**\n")
        
        for schedule in schedules:
            interval = schedule.get('interval', 'Regular')
            timing = schedule.get('km_or_time', '')
            items = schedule.get('items', [])
            
            output.append(f"🔄 **{interval}** ({timing})")
            for item in items:
                output.append(f"   ✓ {item}")
            output.append("")
        
        if notes:
            output.append(f"\n📝 **Catatan**: {notes}")
        
        if source:
            output.append(f"\n📖 Source: {source}")
        
        return "\n".join(output)
    
    @staticmethod
    def format_quick_reference(
        title: str,
        content: Dict,
        source: str = None
    ) -> str:
        """
        Format quick reference card (specifications, torque values, etc)
        
        Args:
            title: Judul reference
            content: Dict {section: [items]} or {key: value}
            source: Sumber dokumen
        
        Returns:
            Formatted reference string
        """
        output = []
        
        output.append(f"**{title}**\n")
        
        if isinstance(content, dict):
            for key, values in content.items():
                output.append(f"**{key}:**")
                if isinstance(values, list):
                    for value in values:
                        output.append(f"   • {value}")
                else:
                    output.append(f"   {values}")
                output.append("")
        
        if source:
            output.append(f"📖 Source: {source}")
        
        return "\n".join(output)
    
    @staticmethod
    def highlight_important(text: str, highlight_phrases: List[str] = None) -> str:
        """
        Add visual emphasis to important phrases
        
        Args:
            text: Original text
            highlight_phrases: Phrases to highlight (optional auto-detection)
        
        Returns:
            Text with highlights
        """
        if highlight_phrases:
            for phrase in highlight_phrases:
                text = text.replace(phrase, f"**{phrase}**")
        
        return text


class ResponseBuilder:
    """Helper class untuk build responses step by step"""
    
    def __init__(self):
        self.sections = []
    
    def add_identification(self, symptom: str) -> 'ResponseBuilder':
        """Add identification section"""
        self.sections.append(f"🔍 **GEJALA**: {symptom}")
        return self
    
    def add_likely_causes(self, causes: List[tuple]) -> 'ResponseBuilder':
        """Add likely causes (name, probability, check_steps)"""
        self.sections.append("🔧 **KEMUNGKINAN PENYEBAB**:")
        for i, (name, prob, steps) in enumerate(causes, 1):
            self.sections.append(f"   {i}. **{name}** ({prob}%)")
            self.sections.append(f"      → Cara check: {steps}")
        return self
    
    def add_procedure(self, steps: List[str]) -> 'ResponseBuilder':
        """Add procedure steps"""
        self.sections.append("🛠️ **PROSEDUR**:")
        for i, step in enumerate(steps, 1):
            self.sections.append(f"   Step {i}: {step}")
        return self
    
    def add_notes(self, **kwargs) -> 'ResponseBuilder':
        """Add notes (time, tools, safety, source)"""
        notes = []
        if 'time' in kwargs:
            notes.append(f"⏱️  {kwargs['time']}")
        if 'tools' in kwargs:
            tools = kwargs['tools']
            tools_str = ", ".join(tools) if isinstance(tools, list) else tools
            notes.append(f"🛠️  {tools_str}")
        if 'safety' in kwargs:
            notes.append(f"⚠️  **SAFETY**: {kwargs['safety']}")
        if 'source' in kwargs:
            notes.append(f"📖 {kwargs['source']}")
        
        if notes:
            self.sections.append("**CATATAN PENTING**:")
            for note in notes:
                self.sections.append(f"   • {note}")
        
        return self
    
    def build(self) -> str:
        """Build final response"""
        return "\n\n".join(self.sections)
