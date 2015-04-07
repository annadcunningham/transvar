import sys, re
from utils import *
from io_utils import *
from err import *
import faidx
from record import *
from collections import deque

def complement(base):

    return {
        'A': 'T',
        'T': 'A',
        'G': 'C',
        'C': 'G',
        'N': 'N'
    }[base]

def reverse_complement(seq):
    
    return ''.join([complement(base) for base in reversed(seq)])


def set_seq(seq, pos, base):

    return ''.join([base if p == pos else b for p, b in enumerate(seq)])

standard_codon_table = {
    'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L', 'TCT': 'S',
    'TCC': 'S', 'TCA': 'S', 'TCG': 'S', 'TAT': 'Y', 'TAC': 'Y',
    'TGT': 'C', 'TGC': 'C', 'TGG': 'W', 'CTT': 'L', 'CTC': 'L',
    'CTA': 'L', 'CTG': 'L', 'CCT': 'P', 'CCC': 'P', 'CCA': 'P',
    'CCG': 'P', 'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
    'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R', 'ATT': 'I',
    'ATC': 'I', 'ATA': 'I', 'ATG': 'M', 'ACT': 'T', 'ACC': 'T',
    'ACA': 'T', 'ACG': 'T', 'AAT': 'N', 'AAC': 'N', 'AAA': 'K',
    'AAG': 'K', 'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
    'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V', 'GCT': 'A',
    'GCC': 'A', 'GCA': 'A', 'GCG': 'A', 'GAT': 'D', 'GAC': 'D',
    'GAA': 'E', 'GAG': 'E', 'GGT': 'G', 'GGC': 'G', 'GGA': 'G',
    'GGG': 'G', 'TAA': '*', 'TAG': '*', 'TGA': '*'}
stop_codons  = [ 'TAA', 'TAG', 'TGA', ]
start_codons = [ 'TTG', 'CTG', 'ATG', ]

def codon2aa(codonseq):
    if codonseq not in standard_codon_table:
        raise IncompatibleTranscriptError('Invalid codon sequence')
    return standard_codon_table[codonseq]

reverse_codon_table = {
    'A': ['GCA', 'GCC', 'GCG', 'GCT'],
    'C': ['TGT', 'TGC'],
    'E': ['GAG', 'GAA'],
    'D': ['GAC', 'GAT'],
    'G': ['GGT', 'GGG', 'GGA', 'GGC'],
    'F': ['TTT', 'TTC'],
    'I': ['ATC', 'ATA', 'ATT'],
    'H': ['CAT', 'CAC'],
    'K': ['AAG', 'AAA'],
    'M': ['ATG'],
    'L': ['CTT', 'CTG', 'CTA', 'CTC', 'TTA', 'TTG'],
    'N': ['AAC', 'AAT'],
    'Q': ['CAA', 'CAG'],
    'P': ['CCT', 'CCG', 'CCA', 'CCC'],
    'S': ['AGC', 'AGT', 'TCT', 'TCG', 'TCC', 'TCA'],
    'R': ['AGG', 'AGA', 'CGA', 'CGC', 'CGG', 'CGT'],
    'T': ['ACA', 'ACG', 'ACT', 'ACC'],
    'W': ['TGG'],
    'V': ['GTA', 'GTC', 'GTG', 'GTT'],
    'Y': ['TAT', 'TAC'],
    '*': ['TAA', 'TAG', 'TGA']
}

def aaseq2nuc(aaseq):

    # only choose first codon
    return ''.join([reverse_codon_table[aa][0] for aa in aaseq if aa in reverse_codon_table])

def aa2codon(aa):
    if aa not in reverse_codon_table:
        raise IncompatibleTranscriptError('Invalid amino acid')
    return reverse_codon_table[aa]

# site in codon follow the genomic order.
# no matter the strand the positive or negative, first site has
# the smallest genomic coordinate
class Codon():
    
    # chrm, locs, strand
    def __init__(self):

        self.gene   = None
        self.chrm   = "NA"
        self.locs   = (-1,-1,-1)
        self.strand = "NA"
        self.seq    = '' # natural sequence, not the actural sequence, can be directly mapped to amino acids
        self.index  = -1

    def refseq(self):

        if self.strand == '+': return self.seq
        else: return reverse_complement(self.seq)

    def aa(self):
        return codon2aa(self.seq)

    def __repr__(self):
        if self.locs:
            return '<Codon %s:%d,%d,%d (%s)>' % (self.chrm, self.locs[0], self.locs[1], self.locs[2], self.strand)
        else:
            return '<Codon unknown>'

    def locformat(self):
        return '-'.join(map(str, self.locs))

    def __eq__(self, other):

        return ((self.chrm, self.strand, self.sites[0].loc) == (other.chrm, other.strand, other.sites[0].loc))

    def __hash__(self):

        return hash((self.chrm, self.sites[0].loc))

    def format(self):
        if self.locs:
            return "%s\t%s\t%s\t%d\t%d\t%d\t%s\t%s" % (self.gene.name, self.index, self.chrm, self.locs[0], self.locs[1], self.locs[2], self.seq, self.strand)
        else:
            return "NA\tNA\tNA\tNA\tNA\tNA\tNA\tNA"

def reverse_tnuc_pos(codon, tnuc_pos):
    
    if codon.strand == '+':
        return codon.locs[(tnuc_pos-1)%3]
    else:
        return codon.locs[2-(tnuc_pos-1)%3]

def codondiff(c1, c2):

    diff = []
    for i in xrange(3):
        if c1[i] != c2[i]:
            diff.append(i)

    return diff

class NonCoding():

    def __init__(self):

        self.gene = None
        self.region = ''
        self.closest_coding_pos = -1
        self.relative_coding_pos = 0

    def format(self):

        return "%s\t%s\t%d\t%d" % (self.gene.name, self.region, self.closest_coding_pos, self.relative_coding_pos)

# def tnuc2gnuc(np, tnuc_pos):
#     """ np is the position array
#     take integer as input
#     """
#     if tnuc_pos >= len(np):
#         raise IncompatibleTranscriptError()
#     return np[tnuc_pos-1]

# def tnuc2gnuc2(np, tnuc_pos, tpt):
#     """ take Pos as input """
#     if tpt.strand == '-':
#         return tnuc2gnuc(np, tnuc_pos.pos) - tnuc_pos.tpos
#     else:
#         return tnuc2gnuc(np, tnuc_pos.pos) + tnuc_pos.tpos

def tnuc_region_in_exon(np, beg, end):
    """ region in tnuc positions """

    if beg.tpos != 0: return False
    if end.tpos != 0: return False
    for i in xrange(beg.pos, end.pos-1):
        if abs(np[i] - np[i+1]) != 1:
            return False
    return True

def tnuc_region_in_intron(np, beg, end):
    """ region in tnuc positions """

    if beg.tpos == 0 or end.tpos == 0: return False
    if beg.pos == end.pos and beg.tpos*end.tpos > 0:
        return True
    if beg.pos+1 == end.pos and beg.tpos>0 and end.tpos<0:
        return True
    if end.pos+1 == beg.pos and beg.tpos<0 and end.tpos>0:
        return True
    return False

def tnuc_range2gnuc_range_(np, tbeg, tend):

    """ convert transcript range to genomic range
    tbeg and tend are 1-based
    """
    return min(np[tbeg-1], np[tend-1]), max(np[tbeg-1], np[tend-1])

class Transcript():

    def __init__(self, transcript_type='protein_coding'):

        """ chrm, strand, start, end, seq (optional), cds_beg, cds_end """

        self.transcript_type = transcript_type
        self.gene   = None
        self.seq    = None
        self.name   = '.'
        self.exons  = []
        self.cds    = []

    def __len__(self):
        if self.seq:
            return len(self.seq)
        else:
            return reduce(lambda x,y: x+y,
                          [end-beg+1 for beg, end in self.exons], 0)

    def format(self):
        # if self.transcript_type == 'protein_coding':
        # return self.name
        # else:
        return '%s (%s)' % (self.name, self.transcript_type)

    def region(self, gnuc_beg, gnuc_end):
        """ annotate genomic region with respect to this transcript """
        # check if gnuc_beg and gnuc_end are inside the genomic region
        pexon = None
        overlapping_exons = []
        for exon in self.exons:
            if (exon[0] <= gnuc_beg and exon[1] >= gnuc_end):
                _cds_beg = min(self.cds_beg, self.cds_end)
                _cds_end = max(self.cds_beg, self.cds_end)
                
                if gnuc_beg > _cds_beg and gnuc_end < _cds_end:
                    return 'Coding'
                elif gnuc_beg < _cds_beg and gnuc_end < _cds_beg:
                    return "5'UTR" if self.strand == '+' else "3'UTR"
                elif gnuc_beg > _cds_end and gnuc_end > _cds_end:
                    return "3'UTR" if self.strand == '+' else "5'UTR"
                elif gnuc_beg < _cds_beg:
                    return "5'UTR;coding" if self.strand == '+' else "3'UTR;coding"
                elif gnuc_end > _cds_end:
                    return "coding;3'UTR" if self.strand == '+' else "coding;5'UTR"
                else:
                    return "Unknown"
            if exon[0] >= gnuc_beg and exon[0] <= gnuc_end:
                overlapping_exons.append(exon)
            if pexon and gnuc_beg > pexon[1] and gnuc_end < exon[0]:
                return 'Intronic'
            pexon = exon

        if overlapping_exons:
            return 'Intronic;Exonic'
        else:
            return 'Unknown'

    def ensure_seq(self):
        """ return True when successful,
        potential reason include patch chromosomes
        """
        if self.seq: return
        if not faidx.refgenome:
            err_die("please provide reference through --ref [reference fasta].")
        seq = faidx.refgenome.fetch_sequence(self.chrm, self.beg, self.end)

        if (not seq) or (len(seq) != self.end - self.beg + 1):
            raise SequenceRetrievalError()
        segs = []
        for ex_beg, ex_end in self.exons:
            beg = max(ex_beg, self.cds_beg)
            end = min(ex_end, self.cds_end)
            if beg <= end:
                segs.append(seq[beg-self.beg:end+1-self.beg])
        self.seq = ''.join(segs)
        if self.strand == '-':
            self.seq = reverse_complement(self.seq)
        return

    def __repr__(self):
        if self.gene:
            return "<Transcript %s %s: %s(%s):%d-%d>" % (self.name, self.gene.name, self.chrm, self.strand, self.beg, self.end)
        else:
            return "<Empty Transcript>"

    def is_standard(self):
        return self == self.gene.std_tpt

    def position_array(self):
        if self.strand == "+":
            np = []
            for beg, end in self.exons:
                np += range(max(beg, self.cds_beg),
                            min(self.cds_end, end)+1)
        else:
            np = []
            for beg, end in reversed(self.exons):
                np += range(min(self.cds_end, end),
                            max(beg, self.cds_beg)-1,-1)

        return np

    def tnuc_range2gnuc_range(self, tbeg, tend):

        """ convert transcript range to genomic range
        tbeg and tend are 1-based
        """
        np = self.position_array()
        return tnuc_range2gnuc_range_(np, tbeg, tend)

    def taa2aa(self, taa):
        self.ensure_seq()
        if taa*3 > len(self.seq):
            raise IncompatibleTranscriptError('Incompatible reference amino acid')
        return codon2aa(self.seq[taa*3-3:taa*3])

    def taa_range2tnuc_seq(self, taa_beg, taa_end):

        if taa_beg*3 > len(self) or taa_end*3 > len(self):
            raise IncompatibleTranscriptError('codon nonexistent')

        self.ensure_seq()
        return self.seq[taa_beg*3-3:taa_end*3]

    def taa_range2aa_seq(self, taa_beg, taa_end):

        return translate_seq(self.taa_range2tnuc_seq(taa_beg, taa_end))

    def tnuc2codon(self, tnuc_pos):
        taa_pos = (tnuc_pos + 2) / 3
        codon = self.cpos2codon(taa_pos)
        pos_r = (tnuc_pos-1) % 3 # 0,1,2 for first, second and third base
        if self.strand == '-': pos_r = 2 - pos_r
        return codon, pos_r, codon.locs[pos_r]

    def _tnuc2gnuc(self, tnuc_pos):
        """ np is the position array
        take integer as input
        """
        self.ensure_position_array()
        if tnuc_pos >= len(self.np):
            raise IncompatibleTranscriptError()
        return self.np[tnuc_pos-1]

    def tnuc2gnuc(self, tnuc_pos):
        """ take Pos as input """
        if self.strand == '-':
            return self._tnuc2gnuc(tnuc_pos.pos) - tnuc_pos.tpos
        else:
            return self._tnuc2gnuc(tnuc_pos.pos) + tnuc_pos.tpos

    def gnuc2exoninds(self, gnuc_beg, gnuc_end): # not used

        exoninds = []
        if self.strand == '+':
            for i, (beg, end) in enumerate(self.exons):
                if tnuc_beg <= end and tnuc_end >= beg:
                    exoninds.append(i)
        else:
            for i, (beg, end) in enumerate(reversed(self.exons)):
                if tnuc_beg <= end and tnuc_end >= beg:
                    exoninds.append(i)

        return exoninds
    
    def _tnuc_range2exon_inds(self, tnuc_beg, tnuc_end):

        exoninds = []
        if self.strand == '+':
            for i, (beg, end) in enumerate(self.exons):
                exoninds.extend([i+1]*(min(self.cds_end, end)-max(beg, self.cds_beg)+1))
        else:
            for i, (beg, end) in enumerate(reversed(self.exons)):
                exoninds.extend([i+1]*(min(self.cds_end, end)-max(beg, self.cds_beg)+1))

        return sorted(list(set(exoninds[tnuc_beg-1:tnuc_end])))


    def tnuc_range2exon_inds(self, tnuc_beg, tnuc_end):

        return ';'.join(map(str, self._tnuc_range2exon_inds(tnuc_beg, tnuc_end)))

    def gnuc_seq2tnuc(self, gnuc_seq):
        if self.strand == '+':
            return gnuc_seq
        else:
            return reverse_complement(gnuc_seq)

    def cpos2aa(self, cpos):
        self.ensure_seq()
        return translate_seq(self.seq[cpos*3-3:cpos*3])

    def cpos2codon(self, cpos):

        """ all coordinates, exons, cds are 1-based
        i.e., (200,300) means the first base is 200
        the last base is 300
        cpos is taa_pos
        """
        self.ensure_seq()
        cpos = int(cpos)
        if self.strand == "+":
            np = []
            for beg, end in self.exons:
                np += range(max(beg, self.cds_beg),
                            min(self.cds_end, end)+1)
            assert len(np) == len(self.seq)

            ni = cpos*3
            if ni <= len(np):
                codon        = Codon()
                codon.index  = cpos
                codon.locs   = tuple(np[ni-3:ni])
                codon.gene   = self.gene
                codon.chrm   = self.chrm
                codon.strand = self.strand
                codon.seq    = self.seq[ni-3:ni]
                return codon
            else:
                raise IncompatibleTranscriptError()
        else:
            np = []
            for beg, end in reversed(self.exons):
                np += range(min(self.cds_end, end),
                            max(beg, self.cds_beg)-1,-1)
            assert len(np) == len(self.seq)

            ni = cpos*3
            if ni <= len(np):
                codon        = Codon()
                codon.index  = cpos
                codon.locs   = tuple(reversed(np[ni-3:ni]))
                codon.gene   = self.gene
                codon.chrm   = self.chrm
                codon.strand = self.strand
                codon.seq    = self.seq[ni-3:ni]
                return codon
            else:
                raise IncompatibleTranscriptError()

    def _init_codon_(self, index):
        c = Codon()
        c.chrm = self.chrm
        c.gene = self.gene
        c.strand = self.strand
        c.index = index
        return c

    def _init_codon2_(self, index):
        c = self._init_codon_(index)
        self.ensure_position_array()
        c.seq = self.seq[index*3-3:index*3]
        c.locs = self.np[index*3-3:index*3]
        return c


    # def _gpos2codon_UTR(self, gpos, np):
    #     """ UTR region """
    #     if self.cds_beg > gpos:
    #         p = Pos(1, gpos-self.cds_beg)
    #         c = self._init_codon_(1)
    #         c.seq = self.seq[:3]
    #         c.locs = np[:3]
    #         reg = '5-UTR' if self.strand == '+' else '3-UTR'
    #         return c, p, reg

    #     if self.cds_end < gpos:
    #         p = Pos(len(self.seq), gpos-self.cds_end)
    #         c = self._init_codon_((len(self.seq)+2)/3)
    #         c.seq = self.seq[c.index*3-3:c.index*3]
    #         c.locs = np[c.index*3-3:c.index*3]
    #         reg = '3-UTR' if self.strand == '+' else '5-UTR'
    #         return c, p, reg
    #     return None

    def describe(self, gpos, args):
        """ determine the position of a single site """

        rg = RegAnno()

        rg.dist2tss = gpos - self.exons[0][0] if self.strand == '+' else self.exons[-1][1] - gpos
        if rg.dist2tss >= -args.prombeg and rg.dist2tss <= args.promend:
            rg.promoter = True
        
        # intergenic, NOTE USE describe_intergenic_neighbors
        if gpos < self.exons[0][0]:
            rg.intergenic = (self.exons[0][0] - gpos, 'upstream' if self.strand == '+' else 'downstream')
            return rg
        if gpos > self.exons[-1][1]:
            rg.intergenic = (gpos - self.exons[-1][1], 'downstream' if self.strand == '+' else 'upstream')
            return rg

        if gpos < self.cds_beg:
            rg.UTR = '5' if self.strand == '+' else '3'
        if gpos > self.cds_end:
            rg.UTR = '3' if self.strand == '+' else '5'

        for i, exon in enumerate(self.exons):
            exind = i+1 if self.strand == '+' else len(self.exons) - i
            if exon[0] <= gpos and exon[1] >= gpos: # exonic
                rg.exonic = True
                if gpos >= self.cds_beg and gpos <= self.cds_end:
                    rg.cds = True
                if gpos == self.cds_beg:
                    rg.start = True
                if gpos == self.cds_end:
                    rg.stop = True
                if gpos == exon[1]:
                    rg.splice = 'NextToDonor' if self.strand == '+' else 'NextToAcceptor'
                if gpos == exon[0]:
                    rg.splice = 'NextToAcceptor' if self.strand == '+' else 'NextToDonor'
                rg.exon = exind
                return rg
            if i > 0:
                pexon = self.exons[i-1]
                if gpos > pexon[1] and gpos < exon[0]: # intronic
                    rg.intronic = True
                    if self.strand == '+':
                        rg.intron_exon1 = exind-1
                        rg.intron_exon2 = exind
                    else:
                        rg.intron_exon1 = exind
                        rg.intron_exon2 = exind+1
                    if gpos in [pexon[1]+1, pexon[1]+2]:
                        rg.splice = 'Donor' if self.strand == '+' else 'Acceptor'
                    if gpos in [exon[0]-2, exon[0]-1]:
                        rg.splice = 'Acceptor' if self.strand == '-' else 'Donor'
                    return rg

        raise Exception()       # you shouldn't reach here

    def describe_span(self, gnuc_beg, gnuc_end, args):

        rg = RegSpanAnno()
        rg.b1 = self.describe(gnuc_beg, args)
        rg.b2 = self.describe(gnuc_end, args)
        rg.transcript_regs = self.overlap_region(gnuc_beg, gnuc_end)

        return rg

    def _gpos2codon_p(self, gpos, np, intronic_policy):

        if gpos < self.cds_beg:
            p = Pos(1, gpos-self.cds_beg)
            c = self._init_codon_(1)
            c.seq = self.seq[:3]
            c.locs = np[:3]
            return c, p

        if gpos > self.cds_end:
            p = Pos(len(self.seq), gpos-self.cds_end)
            c = self._init_codon_((len(self.seq)+2)/3)
            c.seq = self.seq[c.index*3-3:c.index*3]
            c.locs = np[c.index*3-3:c.index*3]
            return c, p
        
        for i, pos in enumerate(np):
            if gpos == pos:
                c = self._init_codon_(i/3+1)
                c.seq    = self.seq[i-i%3:i-i%3+3]
                c.locs   = np[i-i%3:i-i%3+3]
                p = Pos(i+1, 0)
                return c, p
            if gpos < pos:
                
                if ((intronic_policy == 'closer' and gpos-np[i-1] < pos-gpos) or
                    intronic_policy == 'c_smaller'):
                    
                    p = Pos(i, gpos-np[i-1])
                    ci = i/3+1
                    
                elif ((intronic_policy == 'closer' and gpos-np[i-1] >= pos-gpos) or
                      intronic_policy == 'c_greater'):
                    
                    p = Pos(i+1, gpos-pos)
                    ci = (i+1)/3+1
                    
                else:
                    raise Exception()
                            
                c = self._init_codon_(ci)
                c.seq = self.seq[ci*3-3:ci*3]
                c.locs = np[ci*3-3:ci*3]
                return c, p

    def _gpos2codon_n(self, gpos, np, intronic_policy):

        if gpos < self.cds_beg:
            p = Pos(len(self.seq), self.cds_beg-gpos)
            c = self._init_codon_((len(self.seq)+2)/3)
            c.seq = self.seq[c.index*3-3:c.index*3]
            c.locs = np[c.index*3-3:c.index*3]
            return c, p

        if gpos > self.cds_end:
            p = Pos(1, self.cds_end-gpos)
            c = self._init_codon_(1)
            c.seq = self.seq[:3]
            c.locs = np[:3]
            return c, p

        for i, pos in enumerate(np):
            if gpos == pos:
                c = self._init_codon_(i/3+1)
                c.seq = self.seq[i-i%3:i-i%3+3]
                c.locs = tuple(reversed(np[i-i%3:i-i%3+3]))
                p = Pos(i+1, 0)
                return c, p
            
            if gpos > pos:
                
                if ((intronic_policy == 'closer' and np[i-1]-gpos < gpos-pos) or
                    intronic_policy == 'c_smaller'):
                    
                    p = Pos(i, np[i-1]-gpos)
                    ci = i/3+1
                    
                elif ((intronic_policy == 'closer' and np[i-1]-gpos >= gpos-pos) or
                      intronic_policy == 'c_greater'):
                    
                    p = Pos(i+1, pos-gpos)
                    ci = (i+1)/3+1
                    
                else:
                    raise Exception()
                
                c = self._init_codon_(ci)
                c.seq = self.seq[ci*3-3:ci*3]
                c.locs = np[ci*3-3:ci*3]
                return c, p

    def ensure_position_array(self):

        if hasattr(self, 'np'):
            return
        self.ensure_seq()
        self.np = self.position_array()
        assert len(self.np) == len(self.seq)
        return

    def check_exon_boundary(self, pos):
        
        """ check consistency with exon boundary """

        self.ensure_position_array()
        if pos.tpos > 0:
            if abs(self._tnuc2gnuc(pos.pos) - self._tnuc2gnuc(pos.pos+1)) == 1:
                raise IncompatibleTranscriptError()
        elif pos.tpos < 0:
            if abs(self._tnuc2gnuc(pos.pos) - self._tnuc2gnuc(pos.pos-1)) == 1:
                raise IncompatibleTranscriptError()


    def gpos2codon(self, gpos, intronic_policy='closer'):

        """ intronic policy: 
        if gpos falls in intron, 
        closer reports the closer end
        c_smaller reports the smaller cDNA coordinate end
        c_greater reports the greater cDNA coordinate end
        g_smaller reports the smaller gDNA coordinate end
        g_greater reports the greater gDNA coordinate end
        """
        gpos = int(gpos)

        # no check chrm == self.chrm, due to differential
        # naming convention: chr12 vs 12.
        self.ensure_position_array()
        if intronic_policy == 'g_greater':
            intronic_policy = 'c_greater' if self.strand == '+' else 'c_smaller'

        if intronic_policy == 'g_smaller':
            intronic_policy = 'c_smaller' if self.strand == '+' else 'c_greater'
        
        # ret = self._gpos2codon_UTR(gpos, np)
        # if ret: return ret
        if self.strand == "+":
            return self._gpos2codon_p(gpos, self.np, intronic_policy)
        else:
            return self._gpos2codon_n(gpos, self.np, intronic_policy)

    def intronic_lean(self, p, direc):

        self.ensure_position_array()
        if p.tpos == 0:
            c = self._init_codon2_((p.pos+2)/3)
            return (c, p)

        if direc == 'g_greater':
            if self.strand == '+':
                direc = 'c_greater'
            else:
                direc = 'c_smaller'

        if direc == 'g_smaller':
            if self.strand == '+':
                direc = 'c_smaller'
            else:
                direc = 'c_greater'

        if direc == 'c_greater':
            if p.tpos < 0:
                c = self._init_codon2_((p.pos+2)/3)
                return (c, p)
            if p.tpos > 0:
                p = Pos(p.pos+1, p.tpos-abs(self.np[p.pos]-self.np[p.pos-1]))
                c = self._init_codon2_((p.pos+2)/3)
                return (c, p)

        if direc == 'c_smaller':
            if p.tpos > 0:
                c = self._init_codon2_((p.pos+2)/3)
                return (c, p)
            if p.tpos < 0:
                p = Pos(p.pos-1, abs(self.np[p.pos-2]-self.np[p.pos-1])+p.tpos)
                c = self._init_codon2_((p.pos+2)/3)
                return (c, p)

    def overlap_region(self, beg, end):

        if self.beg >= beg and self.end <= end:
            return 'whole'

        coding = False
        intronic = False
        UTR5 = False
        UTR3 = False
        p_ex_end = None
        for ex_beg, ex_end in self.exons:
            if ex_end >= beg and ex_beg <= end:
                if beg < self.cds_beg:
                    if self.strand == '+': UTR5 = True
                    else: UTR3 = True
                if end > self.cds_beg: coding = True
                if end > self.cds_end:
                    if self.strand == '+': UTR3 = True
                    else: UTR5 = True
                if beg < self.cds_end: coding = True
            if p_ex_end and p_ex_end < end and beg < ex_beg:
                # p_ex_end---ex_beg vs beg---end
                intronic = True
            p_ex_end = ex_end

        regc = []
        if self.strand == '+':
            if UTR5: regc.append('UTR5')
            if coding: regc.append('coding')
            if intronic: regc.append('intronic')
            if UTR3: regc.append('UTR3')
        else:
            if UTR3: regc.append('UTR3')
            if coding: regc.append('coding')
            if intronic: regc.append('intronic')
            if UTR5: regc.append('UTR5')

        return regc

    def taa_roll_left_ins(self, index, taa_insseq):

        """ index is the position where the insertion comes after
        """

        self.ensure_seq()
        _taa_insseq_ = deque(taa_insseq)
        while True:
            if index <= 1:
                break
            rightmost = _taa_insseq_[-1]
            left_aa = translate_seq(
                self.seq[(index-1)*3:index*3])
            if rightmost != left_aa:
                break
            _taa_insseq_.pop()
            _taa_insseq_.appendleft(left_aa)
            index -= 1

        return index, ''.join(_taa_insseq_)

    def taa_roll_right_ins(self, index, taa_insseq):

        """ index is the position where the insertion comes after
        """

        self.ensure_seq()
        _taa_insseq_ = deque(taa_insseq)
        taa_len = len(self.seq) / 3
        while True:
            if index + 1 >= taa_len:
                break
            leftmost = _taa_insseq_[0]
            right_aa = translate_seq(
                self.seq[index*3:(index+1)*3])
            # print leftmost, right_aa, index
            if leftmost != right_aa:
                break
            _taa_insseq_.popleft()
            _taa_insseq_.append(right_aa)
            index += 1

        return index, ''.join(_taa_insseq_)

    def taa_roll_3p_ins(self, index, insseq):

        """ roll to 3' """
        if self.strand == '+':
            return self.taa_roll_left_ins(index, insseq)
        else:
            return self.taa_roll_right_ins(index, insseq)

    def taa_roll_left_del(self, taa_beg, taa_end):

        self.ensure_seq()
        while True:
            if taa_beg <= 1:
                break
            left_aa = self.cpos2aa(taa_beg-1)
            rightmost = self.cpos2aa(taa_end)
            if left_aa != rightmost:
                break
            taa_beg -= 1
            taa_end -= 1

        return taa_beg, taa_end

    def taa_roll_right_del(self, taa_beg, taa_end):

        self.ensure_seq()
        taa_len = len(self.seq) / 3
        while True:
            if taa_end + 1 >= taa_len:
                break
            right_aa = self.cpos2aa(taa_end+1)
            leftmost = self.cpos2aa(taa_beg)
            if leftmost != right_aa:
                break
            taa_beg += 1
            taa_end += 1

        return taa_beg, taa_end

    def tnuc_roll_left_ins(self, p, tnuc_insseq):

        """ p is the position where insertion comes after """

        self.ensure_seq()
        _tnuc_insseq_ = deque(tnuc_insseq)
        while True:
            if p <= 1:
                break
            left_base = self.seq[p-1]
            right_most = _tnuc_insseq_[-1]
            # print p, left_base, right_most
            if left_base != right_most:
                break
            _tnuc_insseq_.pop()
            _tnuc_insseq_.appendleft(left_base)
            p -= 1

        return p, ''.join(_tnuc_insseq_)

    def tnuc_roll_right_ins(self, p, tnuc_insseq):

        self.ensure_seq()
        _tnuc_insseq_ = deque(tnuc_insseq)
        tnuc_len = len(self.seq)
        while True:
            if p + 1 >= tnuc_len:
                break
            right_base = self.seq[p]
            left_most = _tnuc_insseq_[0]
            # print p, left_most, right_base
            if right_base != left_most:
                break
            _tnuc_insseq_.popleft()
            _tnuc_insseq_.append(right_base)
            p += 1

        return p, ''.join(_tnuc_insseq_)

    def tnuc_roll_left_del(self, beg, end):

        """ handles exonic region only """

        self.ensure_seq()
        while True:
            if beg <= 1:
                break
            left_base = self.seq[beg-2]
            right_most = self.seq[end-1]
            if left_base != right_most:
                break
            beg -= 1
            end -= 1

        return beg, end

    def tnuc_roll_right_del(self, beg, end):

        self.ensure_seq()
        tnuc_len = len(self.seq)
        while True:
            if end >= tnuc_len - 1:
                break
            right_base = self.seq[end]
            left_most = self.seq[beg-1]
            if right_base != left_most:
                break
            beg += 1
            end += 1

        return beg, end

    def getseq(self, beg, end):

        self.ensure_seq()
        return self.seq[beg-1:end]

    def taa_del_id(self, taa_beg, taa_end):

        if taa_beg == taa_end:
            s = '%s%ddel%s' % (self.cpos2aa(taa_beg), taa_beg, self.taa2aa(taa_beg))
        else:
            taa_del_len = taa_end - taa_beg + 1
            if taa_del_len > delrep_len:
                taa_delrep = str(taa_del_len)
            else:
                taa_delrep = self.taa_range2aa_seq(taa_beg, taa_end)
            s = '%s%d_%s%ddel%s' % (
                self.cpos2aa(taa_beg), taa_beg,
                self.cpos2aa(taa_end), taa_end,
                taa_delrep)

        return s

    def taa_ins_id(self, index, taa_insseq):

        aa = self.cpos2aa(index)
        aa2 = self.cpos2aa(index+1)
        n = len(taa_insseq)
        if index-n+1 > 0:
            flank5_seq = self.taa_range2aa_seq(index-n+1, index)
        else:
            flank5_seq = None

        # if index+n < len(self.seq)/3:
        #     flank3_seq = self.taa_range2aa_seq(index+1, index+n)
        # else:
        #     flank3_seq = None
        if flank5_seq is not None and flank5_seq == taa_insseq:
            if len(flank5_seq) == 1:
                s = '%s%ddup%s' % (aa, index, flank5_seq)
            else:
                s = '%s%d_%s%ddup%s' % (flank5_seq[0], index-n+1, flank5_seq[-1], index, flank5_seq)
        else:
            s = '%s%d_%s%dins%s' % (aa, index, aa2, index+1, taa_insseq)

        return s

    def extend_taa_seq(self, taa_pos_base, old_seq, new_seq):

        taa_pos = None
        termlen = None
        seq_end = self.cds_end
        i = 0
        while True:
            ci = i*3
            old_codon_seq = old_seq[ci:ci+3]
            new_codon_seq = new_seq[ci:ci+3]
            # if sequence comes to ends, extend sequence from reference file
            if (old_codon_seq not in standard_codon_table or 
                new_codon_seq not in standard_codon_table):
                seq_inc = faidx.refgenome.fetch_sequence(self.chrm, seq_end+1, seq_end+100)
                old_seq += seq_inc
                new_seq += seq_inc
                old_codon_seq = old_seq[ci:ci+3]
                new_codon_seq = new_seq[ci:ci+3]
                seq_end += 100

            taa_ref_run = codon2aa(old_codon_seq)
            taa_alt_run = codon2aa(new_codon_seq)
            #print i, old_codon_seq, new_codon_seq, taa_ref_run, taa_alt_run
            if taa_pos == None and taa_ref_run != taa_alt_run:
                taa_pos = i
                taa_ref = taa_ref_run
                taa_alt = taa_alt_run
            if taa_alt_run == '*':
                if taa_pos == None:
                    # Terminating codon encountered before difference
                    return None     # nothing occur to protein level
                termlen = i + 1 - taa_pos
                break
            i += 1

        if taa_pos == None:
            print 'oldseq', old_seq
            print 'newseq', new_seq
        taa_pos += taa_pos_base

        return taa_pos, taa_ref, taa_alt, str(termlen)


def tnuc_del_id(pbeg, pend, tnuc_delseq=None):

    if pbeg == pend:
        tnuc_posstr = str(pbeg)
    else:
        tnuc_posstr = '%s_%s' % (pbeg, pend)

    if tnuc_delseq is None and tnuc_delseq:
        tnuc_delrep = ''
    else:
        if len(tnuc_delseq) > delrep_len:
            tnuc_delrep = str(len(tnuc_delseq))
        else:
            tnuc_delrep = tnuc_delseq

    return '%sdel%s' % (tnuc_posstr, tnuc_delrep)

def gnuc_del_id(chrm, beg, end, gnuc_delseq=None):

    if beg == end:
        gnuc_posstr = str(beg)
    else:
        gnuc_posstr = '%d_%d' % (beg, end)

    if gnuc_delseq is None:
        gnuc_delseq = faidx.getseq(chrm, beg, end)

    del_len = end - beg + 1
    if del_len > delrep_len:
        gnuc_delrep = str(del_len)
    else:
        gnuc_delrep = gnuc_delseq

    return '%sdel%s' % (gnuc_posstr, gnuc_delrep)

def gnuc_roll_left_del(chrm, beg, end):

    """ beg and end are 1st and last base in the deleted sequence """

    sb = faidx.SeqBuf(chrm, beg)
    while True:
        if beg <= 1:
            break
        left_base = sb.get_base(chrm, beg-1)
        rightmost = sb.get_base(chrm, end)
        if left_base != rightmost:
            break
        beg -= 1
        end -= 1

    return beg, end

def gnuc_roll_right_del(chrm, beg, end):

    """ beg and end are 1st and last base in the deleted sequence """

    sb = faidx.SeqBuf(chrm, end)
    chrmlen = faidx.refgenome.chrm2len(chrm)
    while True:
        # check end of chromosome
        if end + 1 >= chrmlen:
            break

        right_base = sb.get_base(chrm, end+1)
        leftmost = sb.get_base(chrm, beg)
        if right_base != leftmost:
            break
        beg += 1
        end += 1

    return beg, end

def gnuc_roll_left_ins(chrm, pos, gnuc_insseq):

    """ pos is where insertion occur after """

    sb = faidx.SeqBuf(chrm, pos)
    _gnuc_insseq_ = deque(gnuc_insseq)
    while True:
        if pos <= 1:
            break
        left_base = sb.get_base(chrm, pos)
        rightmost = _gnuc_insseq_[-1]
        if left_base != rightmost:
            break
        _gnuc_insseq_.pop()
        _gnuc_insseq_.appendleft(left_base)
        pos -= 1

    return pos, ''.join(_gnuc_insseq_)

def gnuc_roll_right_ins(chrm, pos, gnuc_insseq):

    """ pos is where insertion occur after """

    sb = faidx.SeqBuf(chrm, pos)
    chrmlen = faidx.refgenome.chrm2len(chrm)
    _gnuc_insseq_ = deque(gnuc_insseq)
    while True:
        if pos + 1 >= chrmlen:
            break
        right_base = sb.get_base(chrm, pos+1)
        leftmost = _gnuc_insseq_[0]
        if right_base != leftmost:
            break
        _gnuc_insseq_.popleft()
        _gnuc_insseq_.append(right_base)
        pos += 1

    return pos, ''.join(_gnuc_insseq_)

class NucInsertion():

    def __init__(self):
        pass

    def unalign(self):
        
        n = len(self.insseq)
        if self.flank5 == self.insseq:
            if len(self.flank5) == 1:
                return '%sdup%s' % (self.flank5_beg, self.insseq)
            else:
                return '%s_%sdup%s' % (self.flank5_beg, self.flank5_end, self.insseq)
        else:
            return '%s_%sins%s' % (self.beg, self.end, self.insseq)

    def right_align(self):

        n = len(self.insseq_r)
        if self.flank5_r == self.insseq_r:
            if len(self.flank5_r) == 1:
                return '%sdup%s' % (self.flank5_beg_r, self.insseq_r)
            else:
                return '%s_%sdup%s' % (self.flank5_beg_r, self.flank5_end_r, self.insseq_r)
        else:
            return '%s_%sins%s' % (self.beg_r, self.end_r, self.insseq_r)

    def left_align(self):

        n = len(self.insseq_l)
        if self.flank5_l == self.insseq_l:
            if len(self.flank5_l) == 1:
                return '%sdup%s' % (self.flank5_beg_l, self.insseq_l)
            else:
                return '%s_%sdup%s' % (self.flank5_beg_l, self.flank5_end_l, self.insseq_l)
        else:
            return '%s_%sins%s' % (self.beg_l, self.end_l, self.insseq_l)


def gnuc_set_ins(chrm, beg, insseq, r):

    i = NucInsertion()
    i.chrm = chrm
    i.beg = beg
    i.end = beg + 1
    i.insseq = insseq
    n = len(i.insseq)
    i.flank5_beg = i.beg-n+1
    i.flank5_end = i.beg
    i.flank5 = faidx.getseq(chrm, i.flank5_beg, i.flank5_end)
    i.flank3_beg = i.end
    i.flank3_end = i.end+n-1
    i.flank3 = faidx.getseq(chrm, i.flank3_beg, i.flank3_end)
    
    # right align
    i.beg_r, i.insseq_r = gnuc_roll_right_ins(chrm, i.beg, i.insseq)
    i.end_r = i.beg_r + 1
    i.flank5_beg_r = i.beg_r-n+1
    i.flank5_end_r = i.beg_r
    i.flank5_r = faidx.getseq(chrm, i.flank5_beg_r, i.flank5_end_r)
    i.flank3_beg_r = i.end_r
    i.flank3_end_r = i.end_r+n-1
    i.flank3_r = faidx.getseq(chrm, i.flank3_beg_r, i.flank3_end_r)
    
    # left align
    i.beg_l, i.insseq_l = gnuc_roll_left_ins(chrm, i.beg, i.insseq)
    i.end_l = i.beg_l + 1
    i.flank5_beg_l = i.beg_l-n+1
    i.flank5_end_l = i.beg_l
    i.flank5_l = faidx.getseq(chrm, i.flank5_beg_l, i.flank5_end_l)
    i.flank3_beg_l = i.end_l
    i.flank3_end_l = i.end_l+n-1
    i.flank3_l = faidx.getseq(chrm, i.flank3_beg_l, i.flank3_end_l)

    r.gnuc_range = i.right_align()
    r.append_info('left_align_gDNA=g.%s' % i.left_align())
    r.append_info('unalign_gDNA=g.%s' % i.unalign())
    r.append_info('insertion_gDNA='+i.insseq_r)

    return i

def tnuc_set_ins(gi, t, r, beg=None, end=None, insseq=None):

    i = NucInsertion()
    i.chrm = gi.chrm
    if beg is None:
        if t.strand == '+':
            _, i.beg = t.gpos2codon(gi.beg)
        else:
            _, i.beg = t.gpos2codon(gi.end)
    else:
        i.beg = beg

    if end is None:
        if t.strand == '+':
            _, i.end = t.gpos2codon(gi.end)
        else:
            _, i.end = t.gpos2codon(gi.beg)
    else:
        i.end = end

    if t.strand == '+':
        _, i.flank5_beg = t.gpos2codon(gi.flank5_beg)
        _, i.flank5_end = t.gpos2codon(gi.flank5_end)
        _, i.flank3_beg = t.gpos2codon(gi.flank3_beg)
        _, i.flank3_end = t.gpos2codon(gi.flank3_end)
    else:
        _, i.flank5_beg = t.gpos2codon(gi.flank3_end)
        _, i.flank5_end = t.gpos2codon(gi.flank3_beg)
        _, i.flank3_beg = t.gpos2codon(gi.flank5_end)
        _, i.flank3_end = t.gpos2codon(gi.flank5_beg)

    if insseq is None:
        if t.strand == '+':
            i.insseq = gi.insseq
        else:
            i.insseq = reverse_complement(gi.insseq)
    else:
        i.insseq = insseq

    if t.strand == '+':
        i.flank5 = gi.flank5
        i.flank3 = gi.flank3

        _, i.beg_l = t.gpos2codon(gi.beg_l)
        _, i.end_l = t.gpos2codon(gi.end_l)
        i.insseq_l = gi.insseq_l
        i.flank5_l = gi.flank5_l
        i.flank3_l = gi.flank3_l
        _, i.flank5_beg_l = t.gpos2codon(gi.flank5_beg_l)
        _, i.flank5_end_l = t.gpos2codon(gi.flank5_end_l)
        _, i.flank3_beg_l = t.gpos2codon(gi.flank3_beg_l)
        _, i.flank3_end_l = t.gpos2codon(gi.flank3_end_l)


        _, i.beg_r = t.gpos2codon(gi.beg_r)
        _, i.end_r = t.gpos2codon(gi.end_r)
        i.insseq_r = gi.insseq_r
        i.flank5_r = gi.flank5_r
        i.flank3_r = gi.flank3_r
        _, i.flank5_beg_r = t.gpos2codon(gi.flank5_beg_r)
        _, i.flank5_end_r = t.gpos2codon(gi.flank5_end_r)
        _, i.flank3_beg_r = t.gpos2codon(gi.flank3_beg_r)
        _, i.flank3_end_r = t.gpos2codon(gi.flank3_end_r)


    else:
        i.flank5 = reverse_complement(gi.flank3)
        i.flank3 = reverse_complement(gi.flank5)

        _, i.beg_l = t.gpos2codon(gi.end_r)
        _, i.end_l = t.gpos2codon(gi.beg_r)
        i.insseq_l = reverse_complement(gi.insseq_r)
        i.flank5_l = reverse_complement(gi.flank3_r)
        i.flank3_l = reverse_complement(gi.flank5_r)
        _, i.flank5_beg_l = t.gpos2codon(gi.flank3_end_r)
        _, i.flank5_end_l = t.gpos2codon(gi.flank3_beg_r)
        _, i.flank3_beg_l = t.gpos2codon(gi.flank5_end_r)
        _, i.flank3_end_l = t.gpos2codon(gi.flank5_beg_r)

        _, i.beg_r = t.gpos2codon(gi.end_l)
        _, i.end_r = t.gpos2codon(gi.beg_l)
        i.insseq_r = reverse_complement(gi.insseq_l)
        i.flank5_r = reverse_complement(gi.flank3_l)
        i.flank3_r = reverse_complement(gi.flank5_l)
        _, i.flank5_beg_r = t.gpos2codon(gi.flank3_end_l)
        _, i.flank5_end_r = t.gpos2codon(gi.flank3_beg_l)
        _, i.flank3_beg_r = t.gpos2codon(gi.flank5_end_l)
        _, i.flank3_end_r = t.gpos2codon(gi.flank5_beg_l)

    r.tnuc_range = i.right_align()
    r.append_info('left_align_cDNA=c.%s' % i.left_align())
    r.append_info('unalign_cDNA=c.%s' % i.unalign())
    r.append_info('insertion_cDNA='+i.insseq_r)
    return i

def _old_tnuc_set_ins(r, t, p, tnuc_insseq):

    # OBSOLETE !!!
    if p.tpos == 0:
        p1 = p.pos
        # note that intronic indel are NOT re-aligned,
        # because they are anchored with respect to exon boundaries.
        p1r, tnuc_insseq_r = t.tnuc_roll_right_ins(p1, tnuc_insseq)
        r.tnuc_range = '%d_%dins%s' % (p1r, p1r+1, tnuc_insseq_r)
        p1l, tnuc_insseq_l = t.tnuc_roll_left_ins(p1, tnuc_insseq)
        r.append_info('left_align_cDNA=c.%d_%dins%s' % (p1l, p1l+1, tnuc_insseq_l))
        r.append_info('unalign_cDNA=c.%s_%sins%s' % (p1, p1+1, tnuc_insseq))

class Gene():

    def __init__(self, name='', gene_type='protein_coding'):

        self.gene_type = gene_type
        self.name    = name
        self.dbxref  = ''       # for storing GENEID etc.
        self.tpts    = []
        self.std_tpt = None
        self.pseudo  = False

    def __repr__(self):
        return "<Gene: %s>" % self.name

    def longest_tpt(self):

        return max(self.tpts, key=lambda x: len(x))

    def chrm(self):
        
        return self.std_tpt.chrm

    def strand(self):
        
        return self.std_tpt.strand

    def cpos2codon(self, cpos):
        """ based on the longest transcript """

        return self.std_tpt.cpos2codon(cpos)

    def get_beg(self):
        if hasattr(self, 'beg'):
            return self.beg
        else:
            return self.longest_tpt().beg

    def get_end(self):
        if hasattr(self, 'end'):
            return self.end
        else:
            return self.longest_tpt().end

def parse_ucsc_refgene(map_file, name2gene):
    """ start 1-based, end 1-based """

    cnt = 0
    for line in opengz(map_file):
        if line.startswith('#'): continue
        fields = line.strip().split('\t')
        if fields[13] != 'cmpl' or fields[14] != 'cmpl':
            continue
        gene_name = fields[12].upper()
        if gene_name in name2gene:
            gene = name2gene[gene_name]
        else:
            gene = Gene(name=gene_name)
            name2gene[gene_name] = gene
        t = Transcript()
        t.name = fields[1]
        t.chrm = normalize_chrm(fields[2])
        t.strand = fields[3]
        t.beg    = int(fields[4])+1
        t.end    = int(fields[5])
        t.cds_beg = int(fields[6])+1
        t.cds_end = int(fields[7])
        t.source = 'UCSC_refGene'
        ex_begs, ex_ends = fields[9], fields[10]

        for ex_beg, ex_end in zip(map(lambda x: int(x)+1, ex_begs.strip(',').split(',')),
                                  map(int, ex_ends.strip(',').split(','))):
            t.exons.append((ex_beg, ex_end))
            
        t.exons.sort() # keep exons sorted
        gene.tpts.append(t)
        t.gene = gene
        cnt += 1

    err_print('loaded %d transcripts from UCSC refgene.' % cnt)

    return


def parse_ucsc_refgene_customized(map_file, name2gene):

    """ start 1-based, end 1-based """
    cnt = 0
    for line in open(map_file):
        fields = line.strip().split()
        gene_name = fields[0].upper()
        if gene_name in name2gene:
            gene = name2gene[gene_name]
        else:
            gene = Gene(name=gene_name)
            name2gene[gene_name] = gene

        t = Transcript()
        t.chrm = normalize_chrm(fields[1])
        t.strand = fields[2]
        t.beg    = int(fields[3])
        t.end    = int(fields[4])
        t.seq    = fields[-1]
        t.cds_beg = int(fields[5])
        t.cds_end = int(fields[6])
        t.source = 'custom'
        t.name = '.'
        ex_begs, ex_ends = fields[8], fields[9]

        for ex_beg, ex_end in zip(map(int, ex_begs.split(',')),
                                  map(int, ex_ends.split(','))):
            t.exons.append((ex_beg, ex_end))
            
        t.exons.sort() # keep exons sorted
        gene.tpts.append(t)
        t.gene = gene
        cnt += 1

    err_print('loaded %d transcripts from customized table.' % cnt)

    return

class Region():

    def __init__(self, name, beg, end):

        self.name = name
        self.beg = beg
        self.end = end

def parse_refseq_gff(gff_fn, name2gene):

    id2ent = {}
    gff_fh = opengz(gff_fn)
    reg = None
    cnt = 0
    for line in gff_fh:
        if line.startswith('#'): continue
        fields = line.strip().split('\t')
        # print line.strip()
        info = dict([_.split('=') for _ in fields[8].split(';')])
        if fields[2] == 'region':
            if 'chromosome' in info:
                reg = Region(info['chromosome'], int(fields[3]), int(fields[4]))
            # else:
            # reg = None
        elif (reg and fields[2] == 'gene' and
              ('pseudo' not in info or info['pseudo'] != 'true')):
            gene_name = info['Name']
            if gene_name in name2gene:
                g = name2gene[gene_name]
                if hasattr(g, '_gene_id') and g._gene_id != info['ID']:
                    continue   # if a gene_name appears twice, then all the subsequent occurrences are all ignored.
            else:
                g = Gene(name=gene_name)
                name2gene[gene_name] = g
            g._gene_id = info['ID']
            g.beg = int(fields[3])
            g.end = int(fields[4])
            id2ent[info['ID']] = g
            if 'Dbxref' in info:
                g.dbxref = info['Dbxref']

        elif (fields[2] in ['mRNA', 'ncRNA', 'rRNA', 'tRNA']
              and 'Parent' in info and info['Parent'] in id2ent):

            if fields[2] == 'mRNA':
                fields[2] = 'protein_coding'
            if fields[2] == 'ncRNA':
                fields[2] = info['ncrna_class']
            t = Transcript(transcript_type=fields[2])
            t.chrm = normalize_chrm(reg.name)
            t.strand = fields[6]
            t.beg = int(fields[3])
            t.end = int(fields[4])
            t.name = info['Name'] if 'Name' in info else info['product']
            t.gene = id2ent[info['Parent']]
            t.gene.tpts.append(t)
            t.source = 'RefSeq'
            id2ent[info['ID']] = t
            cnt += 1
            
        elif fields[2] == 'exon' and info['Parent'] in id2ent:
            t = id2ent[info['Parent']]
            if (isinstance(t, Gene)):
                g = t
                if not hasattr(g, 'gene_t'):
                    g.gene_t = Transcript()
                    g.tpts.append(g.gene_t)
                    g.gene_t.chrm = normalize_chrm(reg.name)
                    g.gene_t.strand = fields[6]
                    g.gene_t.gene = g
                    g.gene_t.beg = g.beg
                    g.gene_t.end = g.end
                    g.gene_t.source = 'RefSeq'
                    cnt += 1
                t = g.gene_t
            t.exons.append((int(fields[3]), int(fields[4])))
        elif fields[2] == 'CDS' and info['Parent'] in id2ent:
            t = id2ent[info['Parent']]
            if (isinstance(t, Gene)):
                g = t
                if not hasattr(g, 'gene_t'):
                    g.gene_t = Transcript()
                    g.tpts.append(g.gene_t)
                    g.gene_t.chrm = normalize_chrm(reg.name)
                    g.gene_t.strand = fields[6]
                    g.gene_t.gene = g
                    g.gene_t.beg = g.beg
                    g.gene_t.end = g.end
                    g.gene_t.source = 'RefSeq'
                    cnt += 1
                t = g.gene_t
            t.cds.append((int(fields[3]), int(fields[4])))

    err_print("loaded %d transcripts from RefSeq GFF3 file." % cnt)

def parse_ensembl_gtf(gtf_fn, name2gene):
    """ gtf file is gffv2
    parser does not assume order in the GTF file
    """

    gtf_fh = opengz(gtf_fn)
    id2ent = {}
    cnt = 0
    for line in gtf_fh:
        if line.startswith('#'): continue
        fields = line.strip().split('\t')
        info = dict(re.findall(r'\s*([^"]*) "([^"]*)";', fields[8]))
        # info = dict([_.split('=') for _ in fields[8].split(';')])
        if fields[2] == 'gene':
            gene_id = info['gene_id']
            if gene_id not in id2ent:
                id2ent[gene_id] = Gene(gene_type=info['gene_biotype'])
            g = id2ent[gene_id]
            if 'gene_name' in info:
                g.name = info['gene_name'].upper()
            else:
                g.name = gene_id
            if g.name not in name2gene: name2gene[g.name] = g
            g.beg = int(fields[3])
            g.end = int(fields[4])
            
        elif fields[2] == 'transcript':
            tid = info['transcript_id']
            if tid not in id2ent: 
                transcript_type = info['transcript_biotype'] if 'transcript_biotype' in info else info['gene_biotype']
                id2ent[tid] = Transcript(transcript_type=transcript_type)
            t = id2ent[tid]
            t.chrm = normalize_chrm(fields[0])
            t.strand = fields[6]
            t.beg = int(fields[3])
            t.end = int(fields[4])
            t.name = info['transcript_id']
            gene_id = info['gene_id']
            if gene_id not in id2ent:
                id2ent[gene_id] = Gene(gene_type=info['gene_biotype'])
            t.gene = id2ent[gene_id]
            t.gene.tpts.append(t)
            t.source = 'Ensembl'
            cnt += 1
        elif fields[2] == 'exon':
            tid = info['transcript_id']
            if tid not in id2ent:
                transcript_type = info['transcript_biotype'] if 'transcript_biotype' in info else info['gene_biotype']
                id2ent[tid] = Transcript(transcript_type=transcript_type)
            t = id2ent[tid]
            t.exons.append((int(fields[3]), int(fields[4])))
        elif fields[2] == 'CDS':
            tid = info['transcript_id']
            if tid not in id2ent:
                transcript_type = info['transcript_biotype'] if 'transcript_biotype' in info else info['gene_biotype']
                id2ent[tid] = Transcript(transcript_type=transcript_type)
            t = id2ent[tid]
            t.cds.append((int(fields[3]), int(fields[4])))

    err_print("loaded %d transcripts from Ensembl GTF file." % cnt)

def parse_ccds_table(ccds_fn, name2gene):

    """ start 0-based end 0-based """

    ccds_fh = open(ccds_fn)
    ccds_fh.readline()
    cnt = 0
    for line in ccds_fh:
        fields = line.strip().split('\t')
        if fields[5] != 'Public':
            continue
        gene_name = fields[2].upper()
        if gene_name not in name2gene:
            name2gene[gene_name] = Gene(name=gene_name)

        g = name2gene[gene_name]
        t = Transcript()
        t.chrm = normalize_chrm(fields[0])
        t.strand = fields[6]
        t.cds_beg = int(fields[7])+1
        t.cds_end = int(fields[8])+1

        # without UTR information, take CDS boundary as the exon boundary
        t.beg = t.cds_beg
        t.end = t.cds_end

        t.name = fields[4]
        # note that CCDS do not annotate UTR, so all the exons are equivalently cds
        t.exons = [(int(b)+1, int(e)+1) for b,e in re.findall(r"[\s\[](\d+)-(\d+)[,\]]", fields[9])]
        t.source = 'CDDS'
        t.gene = g
        g.tpts.append(t)
        cnt += 1

    err_print("loaded %d transcripts from CCDS table." % cnt)

def parse_ucsc_kg_table(kg_fn, alias_fn, name2gene):

    kg_fh = opengz(kg_fn)
    id2aliases = {}
    if alias_fn:
        alias_fh = opengz(alias_fn)
        for line in alias_fh:
            if line.startswith('#'): continue
            fields = line.strip().split('\t')
            if fields[0] in id2aliases:
                id2aliases[fields[0]].append(fields[1])
            else:
                id2aliases[fields[0]] = [fields[1]]

    cnt = 0
    for line in kg_fh:
        if line.startswith('#'): continue
        fields = line.strip().split('\t')
        g = None
        if fields[0] in id2aliases:
            for alias in id2aliases[fields[0]]:
                if alias in name2gene:
                    g = name2gene[alias]
            if not g:
                g = Gene(name=fields[0])
            for alias in id2aliases[fields[0]]:
                name2gene[alias] = g
        else:
            if fields[0] in name2gene:
                g = name2gene[fields[0]]
            else:
                g = Gene(name=fields[0])
            name2gene[fields[0]] = g

        t = Transcript()
        t.name = fields[0]
        t.chrm = normalize_chrm(fields[1])
        t.strand = fields[2]
        t.beg = int(fields[3])
        t.end = int(fields[4])
        t.cds_beg = int(fields[5])
        t.cds_end = int(fields[6])
        t.source = 'UCSC_knownGene'
        ex_begs, ex_ends = fields[8], fields[9]
        for ex_beg, ex_end in zip(map(int, ex_begs.strip(',').split(',')),
                                  map(int, ex_ends.strip(',').split(','))):
            t.exons.append((ex_beg, ex_end))
        t.exons.sort()
        g.tpts.append(t)
        t.gene = g
        cnt += 1

    err_print("loaded %d transcripts from UCSC knownGene table." % cnt)

def parse_gencode_gtf(gencode_fn, name2gene):

    id2ent = {}
    gencode_fh = opengz(gencode_fn)
    cnt = 0
    for line in gencode_fh:
        # if cnt > 1000:
        #     break
        if line.startswith('#'): continue
        fields = line.strip().split('\t')
        info = dict(re.findall(r'\s*([^"]*) "([^"]*)";', fields[8]))
        if fields[2] == 'gene':
            gene_name = info['gene_name'].upper()
            gid = info['gene_id']
            if gene_name in name2gene:
                g = name2gene[gene_name]
                id2ent[gid] = g
            else:
                if gid not in id2ent:
                    id2ent[gid] = Gene(name=gene_name, gene_type=info['gene_type'])
                g = id2ent[gid]
                name2gene[gene_name] = g
            g.beg = int(fields[3])
            g.end = int(fields[4])
            # if info['gene_type'] == 'pseudogene':
            #     g.pseudo = True
        elif fields[2] == 'transcript':
            tid = info['transcript_id']
            if tid not in id2ent:
                id2ent[tid] = Transcript(transcript_type=info['transcript_type'])
                
            t = id2ent[tid]
            t.chrm = normalize_chrm(fields[0])
            t.strand = fields[6]
            t.beg = int(fields[3])
            t.end = int(fields[4])
            t.name = tid
            gid = info['gene_id']
            if gid not in id2ent:
                id2ent[gid] = Gene(gene_type=info['gene_type'])
            t.gene = id2ent[gid]
            t.gene.tpts.append(t)
            t.source = 'GENCODE'
            id2ent[t.name] = t
            cnt += 1
        elif fields[2] == 'exon':
            tid = info['transcript_id']
            if tid not in id2ent:
                id2ent[tid] = Transcript(transcript_type=info['transcript_type'])
            t = id2ent[tid]
            t.exons.append((int(fields[3]), int(fields[4])))
        elif fields[2] == 'CDS':
            tid = info['transcript_id']
            if tid not in id2ent:
                id2ent[tid] = Transcript(transcript_type=info['transcript_type'])
            if tid not in id2ent: id2ent[tid] = Transcript()
            t = id2ent[tid]
            t.cds.append((int(fields[3]), int(fields[4])))

    err_print("loaded %d transcripts from GENCODE GTF file." % cnt)

def parse_aceview_transcripts(aceview_gff_fn, name2gene):

    id2tpt = {}
    aceview_fh = opengz(aceview_gff_fn)
    for line in aceview_fh:
        if line.startswith('#'): continue
        fields = line.strip().split('\t')
        if len(fields) < 9: continue # the old transcript definition (hg18) from AceView is a bit corrupted.
        info = dict(re.findall(r'\s*(\S+) (\S+);', fields[8]))
        if fields[2] == 'CDS':
            gene_name = info['gene_id'].upper()
            if gene_name in name2gene:
                g = name2gene[gene_name]
            else:
                g = Gene(name=gene_name)
                name2gene[gene_name] = g

            if info['transcript_id'] in id2tpt:
                t = id2tpt[info['transcript_id']]
            else:
                t = Transcript()
                t.chrm = normalize_chrm(fields[0])
                t.strand = fields[6]
                t.name = info['transcript_id']
                id2tpt[t.name] = t
                t.gene = g
                g.tpts.append(t)
                t.source = 'AceView'

            t.cds.append((int(fields[3]), int(fields[4])))

        elif fields[2] == 'exon':
            gene_name = info['gene_id'].upper()
            if gene_name in name2gene:
                g = name2gene[gene_name]
            else:
                g = Gene(name=gene_name)
                name2gene[gene_name] = g

            if info['transcript_id'] in id2tpt:
                t = id2tpt[info['transcript_id']]
            else:
                t = Transcript()
                t.chrm = normalize_chrm(fields[0])
                t.strand = fields[6]
                t.name = info['transcript_id']
                id2tpt[t.name] = t
                t.gene = g
                g.tpts.append(t)
                t.source = 'AceView'

            t.exons.append((int(fields[3]), int(fields[4])))

    # skip transcripts without CDS, e.g., LOC391566.aAug10-unspliced
    for tid, t in id2tpt.iteritems():
        if t.cds and t.exons:
            t.exons.sort()
            t.beg = t.exons[0][0]
            t.end = t.exons[-1][1]
        else:
            t.gene.tpts.remove(t)

    err_print("loaded %d transcripts from AceView GFF file." % len(id2tpt))

def parse_uniprot_mapping(fn):

    tid2uniprot = {}
    for line in opengz(fn):
        fields = line.strip().split('\t')
        tid2uniprot[fields[2]] = fields[0]

    err_print('loaded %d transcript with UniProt mapping.' % len(tid2uniprot))

    return tid2uniprot

def translate_seq(seq):

    if len(seq) % 3 != 0:
        raise IncompatibleTranscriptError('translated coding sequence not multiplicative of 3, most likely a truncated sequence.')

    aa_seq = []
    for i in xrange(len(seq)/3):
        aa = codon2aa(seq[i*3:i*3+3])
        aa_seq.append(aa)
        if aa == '*':
            break

    return ''.join(aa_seq)
