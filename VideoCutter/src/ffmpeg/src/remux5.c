/*
 * MPEG muxer/cutter
 * Copyright (c) 2018 Kanehekili
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */
 /*
  * ~/JWSP/FFMPEG/remux5 nano.m2t 000.mp4 > decode5.txt
  * /home/matze/Videos/3sat_HD-test/nano.m2t /home/matze/Videos/3sat_HD-test/000.mp4  -s 385.980,415.205,510.83,530.00
  * /home/matze/Videos/3sat_HD-test/nano.m2t /home/matze/Videos/3sat_HD-test/000.mp4
  */
#include <libavutil/timestamp.h>
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/opt.h>
#include <libavutil/frame.h>
#include <libavutil/mathematics.h>
#include <unistd.h>
#include <stdio.h>

struct StreamInfo{
    int srcIndex; //Index of ifmt_ctx stream
    int dstIndex; //Index of out stream. TODO - currently 0: video, 1: audio
    int64_t currentDTS; //for keeping 
    AVStream *outStream;
    AVStream *inStream;
    AVCodecContext *codec_ctx; //Decode
    AVCodecContext *out_codec_ctx; //Encode
    AVOutputFormat *ofmt;
    //AVRational codec_time;//like 1800 or 1536...
	AVRational in_time_base;
	AVRational out_time_base;
	int64_t first_dts;
};

typedef struct {
    
    AVFormatContext *ifmt_ctx;
    AVFormatContext *ofmt_ctx;
    int64_t frame_number;
    int64_t gap; //sync cutting gaps
	int64_t streamOffset; //the offset between audio and video stream.
 
} SourceContext;

typedef struct {
    int64_t start;
    int64_t end;
    int64_t pts;
    int64_t dts;
    int gopSize;
} CutData;

/*** globals ****/
    struct StreamInfo *videoStream;
    struct StreamInfo *audioStream;
    SourceContext context;

/*** Basic stuff ***/
double_t timeFromPTS(int64_t delta, AVRational time_base){
    double_t res = (double_t)delta*time_base.num/time_base.den;
    return res;
}

int64_t ptsFromTime(double_t ts,AVRational time_base){
    int64_t res = (int64_t)(ts*time_base.den/time_base.num);
    return res;
}


static int findBestVideoStream(struct StreamInfo *info){//enum AVMediaType type
    info->srcIndex = av_find_best_stream(context.ifmt_ctx,AVMEDIA_TYPE_VIDEO,-1,-1,NULL,0);
    info->inStream=context.ifmt_ctx->streams[info->srcIndex];
    info->dstIndex=0; //May be a hack?
    info->in_time_base=info->inStream->time_base;
    return info->srcIndex;
}

static int findBestAudioStream(struct StreamInfo *info){
    info->srcIndex = av_find_best_stream(context.ifmt_ctx,AVMEDIA_TYPE_AUDIO,-1,-1,NULL,0);
    if (AVERROR_STREAM_NOT_FOUND == info->srcIndex){
        fprintf(stderr, "No audio stream found\n");
        return -1;
    }
    if (AVERROR_DECODER_NOT_FOUND == info->srcIndex){
        fprintf(stderr, "No audio decoder found\n");
        return -1;
    }
    info->inStream=context.ifmt_ctx->streams[info->srcIndex];//TODO function in struct?
    info->dstIndex=1;//TODO more to come
    info->in_time_base=info->inStream->time_base;
    return info->srcIndex;
}

static int searchVideoFilters(struct StreamInfo *info){
   info->ofmt= NULL;
   int codecID = info->inStream->codecpar->codec_id;
   if (codecID == AV_CODEC_ID_MPEG2VIDEO){
        info->ofmt= av_guess_format("dvd", NULL, NULL);
        printf("MPEG2 set to -f dvd\n");
    }//else if (codecID == AV_CODEC_ID_H264) {
//        info->ofmt= av_guess_format("mpegts", NULL, NULL);
//        printf("MPEG4 set to -f mpts\n");
//    }
    return 1;
}

static int searchAudioFilters(struct StreamInfo *info){
    //TODO aac_adtstoasc: return self.getAudioStream().getCodec() =="aac" and (self.isH264() or self.isMP4())
    return 1;
}


static int createOutputStream(struct StreamInfo *info){
    AVStream *out_stream;
    AVCodecParameters *pCodecParm = info->inStream->codecpar;
 
    out_stream = avformat_new_stream(context.ofmt_ctx, NULL);
    if (!out_stream) {
        fprintf(stderr, "Failed allocating output stream\n");
        return AVERROR_UNKNOWN;
    }

    int ret = avcodec_parameters_copy(out_stream->codecpar, pCodecParm);
    if (ret < 0) {
        fprintf(stderr, "Failed to copy codec parameters\n");
        return ret;
    }
    out_stream->codecpar->codec_tag = 0;
    out_stream->start_time=0;//AV_NOPTS_VALUE;
    out_stream->duration=0;
    //NOT PUBLIC?av_stream_set_r_frame_rate(out_stream,info->inStream->r_frame_rate);//????
    out_stream->avg_frame_rate = info->inStream->avg_frame_rate;
    
    if (pCodecParm->codec_type==AVMEDIA_TYPE_AUDIO){
        out_stream->codecpar->frame_size = 2048;//TODO AAC: 1024*channels == 2048, mp3 =1152*channels =2304...
    }
    info->outStream=out_stream;
    return 1;
}

int _initOutputContext(char *out_filename){
    AVFormatContext *ofmt_ctx = NULL; 
    AVOutputFormat *ofmt = NULL;
    int ret;
    
    ret= avformat_alloc_output_context2(&ofmt_ctx, videoStream->ofmt, NULL, out_filename);
    if (!ofmt_ctx || ret < 0) {
        fprintf(stderr, "Could not create output context\n");
        return -1;
    }
 
    //https://stackoverflow.com/questions/40991412/ffmpeg-producing-strange-nal-suffixes-for-mpeg-ts-with-h264?rq=1
    ofmt_ctx->flags |= AVFMT_FLAG_KEEP_SIDE_DATA;
  

    context.ofmt_ctx = ofmt_ctx;
    videoStream->ofmt = ofmt_ctx->oformat;    
    ofmt = ofmt_ctx->oformat;

    if ((ret = createOutputStream(videoStream))< 0){
        fprintf(stderr, "Could not create video output \n");
        return -1;
    }
     AVRational frameRate = av_stream_get_r_frame_rate(videoStream->inStream);
     int64_t bitrate = context.ifmt_ctx->bit_rate;
     printf("Video: frame rate: %d/%d bitrate: %ld \n",frameRate.num,frameRate.den,bitrate);
     ofmt_ctx->bit_rate = bitrate;
     //av_stream_set_r_frame_rate(videoStream->outStream,frameRate);
    /* The VBV Buffer warning is removed: */
    AVCPBProperties *props;
	props = (AVCPBProperties*) av_stream_new_side_data(videoStream->outStream, AV_PKT_DATA_CPB_PROPERTIES, sizeof(*props));
	int64_t bit_rate = context.ifmt_ctx->bit_rate;

	props->buffer_size = 1024 *1024;
	props->max_bitrate = 15*bit_rate;
	props->min_bitrate = (2*bit_rate)/3;
	props->avg_bitrate = bit_rate;
	props->vbv_delay = UINT64_MAX;

         
    if (audioStream->srcIndex>=0) {
        if ((ret = createOutputStream(audioStream))< 0){
            fprintf(stderr, "Could not create video output \n");
            return -1;
        }
		int sampleRate = audioStream->inStream->codecpar->sample_rate;   
		bitrate = audioStream->inStream->codecpar->bit_rate;
		printf("Audio: sample rate: %d bitrate: %ld\n",sampleRate,bitrate);
     }

    av_dump_format(ofmt_ctx, 0, out_filename, 1);

    if (!(ofmt->flags & AVFMT_NOFILE)) {
        ret = avio_open(&ofmt_ctx->pb, out_filename, AVIO_FLAG_WRITE);
        if (ret < 0) {
            fprintf(stderr, "Could not open output file '%s'", out_filename);
            return -1;
        }
     }


    ret = avformat_write_header(ofmt_ctx, NULL);
    if (ret < 0) {
        fprintf(stderr, "Error occurred when opening output file\n");
        return -1;
    }

	videoStream->out_time_base=videoStream->outStream->time_base;
	audioStream->out_time_base=audioStream->outStream->time_base;
    return 1;
}

int _setupStreams(char *in_filename, char *out_filename){
    int ret;
    AVFormatContext *ifmt_ctx = NULL;
    
    if ((ret = avformat_open_input(&ifmt_ctx, in_filename, 0, 0)) < 0) {
        fprintf(stderr, "Could not open input file '%s'", in_filename);
        return -1;
    }

    if ((ret = avformat_find_stream_info(ifmt_ctx,NULL)) < 0) {
        fprintf(stderr, "Failed to retrieve input stream information");
        return -1;
    }

    av_dump_format(ifmt_ctx, 0, in_filename, 0);
   
    context.ifmt_ctx = ifmt_ctx;
    //Later we take all audio streams.
    if ((ret = findBestVideoStream(videoStream)) < 0) {
        printf("No video stream found \n");
    }
    if ((ret = findBestAudioStream(audioStream)) < 0) {
       printf("No audio stream found \n");
    }
    
    if ((ret = searchVideoFilters(videoStream))< 0){
        fprintf(stderr, "Failed to retrieve video filter");
        return -1;        
    }
    if (audioStream->srcIndex >=0) {
        if ((ret = searchAudioFilters(audioStream))< 0){
            fprintf(stderr, "Failed to retrieve audio filter");
            return -1;        
        }
    }
    return _initOutputContext(out_filename);
}

static int _initDecoder(struct StreamInfo *info){
    AVCodec *dec = NULL;
    AVCodecContext *dec_ctx = NULL;
    AVDictionary *opts = NULL;
    
    int ret;
    dec = avcodec_find_decoder(info->inStream->codecpar->codec_id);
    if (!dec) {
        fprintf(stderr, "Failed to find %s codec\n",av_get_media_type_string(AVMEDIA_TYPE_VIDEO));
        return -1;
    } 
    
    /* Allocate a codec context for the decoder */
    dec_ctx = avcodec_alloc_context3(dec);
    if (dec_ctx == NULL){
       fprintf(stderr, "Failed to alloc codec context\n");
       return -1;
    }
    avcodec_parameters_to_context(dec_ctx, info->inStream->codecpar);
    av_dict_set(&opts, "refcounted_frames","1",0);
    dec_ctx->framerate = av_guess_frame_rate(context.ifmt_ctx, info->inStream, NULL);

    if ((ret=avcodec_open2(dec_ctx,dec,&opts))<0){ 
       fprintf(stderr, "Failed to open codec context\n");
       return -1;
    }
    info->codec_ctx=dec_ctx;
   
    return 1;
}

/**************** MUXING SECTION ***********************/
static int seekGOPs(struct StreamInfo *info, int64_t ts,CutData *borders) {
    AVPacket pkt;
    int64_t lookback=ptsFromTime(1.0,info->inStream->time_base);
    int keyIndex=0;
    int keyFrameCount=0;
    int64_t gop[2]={0,0};
    int64_t last_dts=0;
    int gopSize=0;
    //DEbug only
    //int64_t vStreamOffset = videoStream->inStream->start_time;
    //double_t streamOffset = timeFromPTS(vStreamOffset,info->inStream->time_base);
    if (lookback > ts)
        lookback=ts;
    //const int genPts= context.ifmt_ctx->flags & AVFMT_FLAG_GENPTS; alway 0->so packet buffer is used
    av_init_packet(&pkt);
    if(av_seek_frame(context.ifmt_ctx, info->srcIndex, ts-lookback, AVSEEK_FLAG_BACKWARD) < 0){
        printf("av_seek_frame failed.\n");
        return -1;
    }
   
     while (av_read_frame(context.ifmt_ctx, &pkt)>=0 && keyFrameCount < 4) {
        if (pkt.stream_index != info->srcIndex){
            av_packet_unref(&pkt); 
            continue;
        }
        if (pkt.flags == AV_PKT_FLAG_KEY){
            if (keyIndex){
                gop[keyIndex]=last_dts; //up to not including the I Frame....
                break;
            }else
              gop[keyIndex]=pkt.dts;
            gopSize=0; 
            keyFrameCount++;//More than 4 GOPs are error.               
        }
        gopSize++;
        last_dts = pkt.dts;
      
        if (pkt.dts >= ts &&!keyIndex){
            keyIndex=1;
            borders->dts=pkt.dts;
            borders->pts=pkt.pts;
        }
        
        av_packet_unref(&pkt); 
     }   

     av_packet_unref(&pkt); 
     borders->start=gop[0];
     borders->end=gop[1];
     borders->gopSize=gopSize;
     
     printf("GOP size %d, search > %ld found: %ld (keycount %d) start: %ld end %ld \n",gopSize,ts,borders->dts,keyFrameCount,gop[0],gop[1]);
     return keyFrameCount<4;
}

/** Write packet to the out put stream. Here we calculate the PTS/dts. Only Audio and video streams are incoming  **/
static int write_packet(struct StreamInfo *info,AVPacket *pkt,CutData head,CutData tail){ //cut data  obsolete!
        AVStream *in_stream = NULL, *out_stream = NULL;
         
        char frm='*';
        int isVideo = videoStream->srcIndex==pkt->stream_index;
        if (isVideo) {
            context.frame_number+=1;   
            if (pkt->flags == AV_PKT_FLAG_KEY)
                frm='I';      
            else
                frm='v';      
        }else {//Audio
            frm='*';        
        }
        
        in_stream  = info->inStream;
        out_stream  = info->outStream;
        
        /**
         * Cutting data is in video time. Convert it from video time to stream time.
         * To have a zero based dts without gaps the follwing rule is applied:
         * dts-(cumulated gaps + dts of the start of first cut - the stream offset between video and audio)
         * The offset prevents too many negative TS at the start of the stream that lies behind timewise
         * It is the difference between video and the "latest" audio in DTS.
         */
		int64_t	cum =  context.gap+info->first_dts - context.streamOffset ;		
        int64_t offset = av_rescale_q(cum,videoStream->inStream->time_base, in_stream->time_base);
        int64_t new_DTS = pkt->dts - offset ;
        /* save original packet dates*/
        int64_t p1 = pkt->pts;
        int64_t d1 = pkt->dts;
        int64_t delta = p1-d1;
        int64_t dur = pkt->duration;
        
        //happens
        if (p1==AV_NOPTS_VALUE){
			delta = 0;//or dur? bei mp2 auf jeden fall ok
		}
        
        //double_t testTS = av_q2d(videoStream->inStream->time_base)*(pkt->dts - offset);
        double_t testTS = av_q2d(videoStream->inStream->time_base)*new_DTS;
        
        if (new_DTS<0){
			printf("Drop neg packet: %c: dts:%ld (%ld) time: %.3f, offs: %ld\n",frm,new_DTS,pkt->dts,testTS,offset);
			av_packet_unref(pkt);
			return 1;
		}

/* Seen in doxygen examples:
 * typedef struct StreamContext {
    AVCodecContext *enc_ctx;
    ->tb of CodecContext ENCODER or CC created with avcodec_alloc_codec3 & tb of stream
    av_packet_rescale_ts(&enc_pkt,
                         stream_ctx[stream_index].enc_ctx->time_base,
                         ofmt_ctx->streams[stream_index]->time_base);
 */ 

        pkt->stream_index = info->dstIndex;
        //from remuxing: = av_rescale_q_rnd(pkt.pts, in_stream->time_base, out_stream->time_base, AV_ROUND_NEAR_INF|AV_ROUND_PASS_MINMAX);
        pkt->pts = av_rescale_q(new_DTS + delta,in_stream->time_base, out_stream->time_base);
        pkt->dts = av_rescale_q(new_DTS,in_stream->time_base, out_stream->time_base);
        pkt->duration = av_rescale_q(pkt->duration, in_stream->time_base, out_stream->time_base);
        pkt->pos=-1;//File pos is unknown if cut..
        double_t testTS2 = av_q2d(out_stream->time_base)*pkt->dts;//==dtsCalcTime!
		//if (d1 < head.start){
		if(pkt->dts < info->currentDTS){
                //int64_t relHead = av_rescale_q(head.start,videoStream->inStream->time_base, in_stream->time_base);
				printf("Drop early packet: %c: dts:%ld (%ld) timeOut %.3f timeIn: %.3f currDTS: %ld\n",frm,pkt->dts,d1,testTS2,testTS,info->currentDTS);
				av_packet_unref(pkt);
				return 1;
		}

        info->currentDTS = pkt->dts+pkt->duration;
        
        double_t dtsCalcTime = av_q2d(out_stream->time_base)*pkt->dts;
        double_t ptsCalcTime = av_q2d(out_stream->time_base)*pkt->pts;
        
        printf("%ld,%c:",context.frame_number,frm);
        printf("P:%ld (%ld) D:%ld (%ld) Pt:%.3f Dt:%.3f idx: (%d) dur %ld (%ld) size: %d flags: %d\n",pkt->pts,p1,pkt->dts,d1,ptsCalcTime,dtsCalcTime,pkt->stream_index ,pkt->duration,dur,pkt->size,pkt->flags);

        int ret = av_interleaved_write_frame(context.ofmt_ctx, pkt);
        //int ret = av_write_frame(context.ofmt_ctx, pkt);
        if (ret < 0) {
            fprintf(stderr, "Error muxing packet\n");
            return ret;
        }
        av_packet_unref(pkt);
        return 1;
        
}

//Plain muxing, no encoding yet
static int mux1(CutData head,CutData tail){
    struct StreamInfo *streamInfo;
    AVPacket pkt = { .data = NULL, .size = 0 };
    int64_t dts=0;
    av_init_packet(&pkt);
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
        //int isKeyFrame = pkt.flags == AV_PKT_FLAG_KEY;
        int streamIdx = pkt.stream_index;
        int isVideo = streamIdx == videoStream->srcIndex;
        int isAudio = streamIdx == audioStream->srcIndex;
        if (isVideo){
            streamInfo = videoStream;
            dts=pkt.dts;
        } else if (isAudio ) {
            streamInfo = audioStream;
        } else {
          av_packet_unref(&pkt);
          continue; //No usable packet.
        }  
        write_packet(streamInfo,&pkt,head,tail);
        if (dts >= tail.end){
            break;
		}

    }
    av_packet_unref(&pkt);
    return 1;
}


/** decode the input stream, display its data **/
static int dumpDecodingData(){
    struct StreamInfo *streamInfo;
	char frm;
    AVPacket pkt;
    int64_t frame_number=0;
    pkt.data = NULL;
    pkt.size = 0;
    av_init_packet(&pkt); 
    
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {

        int isVideo = videoStream->srcIndex==pkt.stream_index;
        if (isVideo) {
			frame_number++;
            streamInfo = videoStream;
            context.frame_number+=1;   
            if (pkt.flags == AV_PKT_FLAG_KEY)
                frm='I';      
            else
                frm='v';      
        }else {//Audio
            frm='*';        
            streamInfo = audioStream;
        }		
        int64_t streamOffset = streamInfo->inStream->start_time;
//TODO: PRINT OUT THE STUFF == ANALYSE
       double_t dtsCalcTime = av_q2d(streamInfo->outStream->time_base)*pkt.dts;
        double_t ptsCalcTime = av_q2d(streamInfo->outStream->time_base)*pkt.pts;
        double_t xxx = av_q2d(streamInfo->inStream->time_base)*(pkt.pts-streamOffset);
        
        
        printf("%ld,%c:",frame_number,frm);
        printf("P:%ld  D:%ld Pt:%.3f Dt:%.3f X: %.3f dur %ld \n",pkt.pts,pkt.dts,ptsCalcTime,dtsCalcTime,xxx,pkt.duration);

          av_packet_unref(&pkt);
    }
    return 1;                
}
/*
 * tb=90000
start1=6138895457 = head1
tail1=6141536057
head2=6170647457
gap1=(head2-tail1)

head2-gap1-start1
2640600
2640600/tb
29.340 QED
 */
/** seek to the timeslots and cut them out **/
static int seekAndMux(double_t timeslots[],int seekCount){
    AVRational time_base = videoStream->in_time_base;
    int64_t vStreamOffset = videoStream->inStream->start_time;
    int64_t aStreamOffset = audioStream->inStream->start_time;
    int64_t startOffset = vStreamOffset - aStreamOffset;
    double_t streamOffsetTime = av_q2d(time_base)*startOffset;
    double_t vStreamStartTime = av_q2d(time_base)*vStreamOffset;
    double_t aStreamStartTime = av_q2d(time_base)*aStreamOffset;
    int64_t duration = videoStream->inStream->duration;


    CutData headBorders;
    CutData tailBorders;

    printf("Mux video: %ld (%.3f) audio: %ld (%.3f) delta:%ld (%.3f) \n",vStreamOffset,vStreamStartTime,aStreamOffset,aStreamStartTime,startOffset,streamOffsetTime);
    printf("Video tbi: %d tbo; %d audio tbi: %d tbo: %d \n",time_base.den,audioStream->in_time_base.den,videoStream->out_time_base.den,audioStream->out_time_base.den);
    printf("Video IN: %s long:%s\n",context.ifmt_ctx->iformat->name,context.ifmt_ctx->iformat->long_name);
    if (context.ofmt_ctx)
        printf("Video OUT: %s long:%s\n",context.ofmt_ctx->oformat->name,context.ofmt_ctx->oformat->long_name);

    context.streamOffset = startOffset; 
	int startSet=0;
	int64_t prevTail =0;
	int64_t gap =0;
    int i;
    for (i = 0; i < (seekCount); ++i){
        double_t startSecs = timeslots[i];
        double_t endSecs = timeslots[++i];
        if (endSecs < startSecs)
            endSecs=startSecs+duration;
            
        int64_t ptsStart = ptsFromTime(startSecs+vStreamStartTime,time_base);
        int64_t ptsEnd = ptsFromTime(endSecs+vStreamStartTime,time_base);
        printf("Search from %.3f to %.3f pts: %ld - %ld \n",startSecs,endSecs,ptsStart,ptsEnd);
        seekGOPs(videoStream,ptsStart,&headBorders);//Header GOP
        seekGOPs(videoStream,ptsEnd,&tailBorders); //TAIL GOP
        int64_t head = headBorders.start;
        if (!startSet){
			videoStream->first_dts =head;
			audioStream->first_dts =head;
			prevTail=head;
			startSet=1;
		}
		gap += (head-prevTail);
        context.gap = gap;
        printf("Gap calc <tail %ld head: %ld gap: %ld dts-v-offset %ld a-offset %ld\n",prevTail,head,context.gap,videoStream->first_dts,audioStream->first_dts);
        prevTail = tailBorders.end;
        
        if (headBorders.start == headBorders.end || tailBorders.start==tailBorders.end){
            fprintf(stderr,"Seek times out of range. Aborted");
            return -1;
        }
        
         if(av_seek_frame(context.ifmt_ctx, videoStream->srcIndex, headBorders.start, AVSEEK_FLAG_ANY) < 0){
            fprintf(stderr,"av_seek_frame failed.\n");
            return -1;
        }
        avcodec_flush_buffers(videoStream->codec_ctx);
        //Start of an I frame we are.
        if (mux1(headBorders,tailBorders) < 0){
            printf("muxing failed\n");
            return -1;
        }
        context.streamOffset+=9000; //TEST for gap
    }
    return 1;    
}


/******************** Main helper *************************/
int parseArgs(int argc, char *argv[],double_t array[]) {
  int c,i, count;
  opterr = 0;
  count=0;
  while ((c = getopt (argc, argv, "?s:d")) != -1){
        switch (c){
          case 's':
              i = 0;
              char *tmp;
              tmp = strtok(optarg,",");
              while (tmp != NULL) {
                array[i++]= atof(tmp);
                tmp = strtok(NULL,","); 
              }
              count=i;
              break;
          case 'd':
            av_log_set_level(AV_LOG_DEBUG);
            break;
          case '?':
            printf("*************Seek and info feature for video streams************\n");
            printf("-s: \tseek to a dts timetamp in seconds\n");
            //exit(EXIT_FAILURE);
            return -1;
          default:
            printf("that dont work\n");
            return -1;
         }
  }
  return count; 
}
static int shutDown(int ret){
    AVOutputFormat *ofmt = NULL;
    AVFormatContext *ofmt_ctx = NULL;
    ofmt_ctx = context.ofmt_ctx;
    if (ofmt_ctx == NULL) {
        return 1;
    }

    ofmt = ofmt_ctx->oformat;
     /* close input */
    avformat_close_input(&context.ifmt_ctx);
     /* close output */
    if (ofmt_ctx && !(ofmt->flags & AVFMT_NOFILE))
        avio_closep(&ofmt_ctx->pb);
    avformat_free_context(ofmt_ctx);
    
    if (ret < 0 && ret != AVERROR_EOF) {
        fprintf(stderr, "Error occurred: %s\n", av_err2str(ret));
        return 1;
    }
    return 0;
}

/****************** MAIN **************************/
int main(int argc, char **argv)
{
    double_t timeslots[255];
    int seekCount;
    int ret;
    char *in_filename;
    char *out_filename;
    
	videoStream = malloc(sizeof(*videoStream));
    audioStream = malloc(sizeof(*audioStream));
    if (argc < 3) {
        printf("usage: %s input output -s time,time,time,time.....\n"
               "Remux a media file with libavformat and libavcodec.\n"
               "The output format is guessed according to the file extension.\n"
               "-s: Set the time in seconds.millis for start & stop of a chunk\n"
               "-d: debug mode\n"
               "\n", argv[0]);
        return 1;
    }
    in_filename = argv[1];
    out_filename= argv[2];
    printf("Args: %s %s flags: %s %s\n",argv[1],argv[2],argv[3],argv[4]);

    //The seeks slots...
    seekCount = parseArgs(argc,argv,timeslots);

    if ((ret=_setupStreams(in_filename,out_filename))<0)
        return shutDown(ret);
        
    if (seekCount == 0)
        ret= dumpDecodingData();
    else {
        //TODO DEcoder/encoder
        if (videoStream->srcIndex>=0){
            _initDecoder(videoStream);
        }
        /** ENTER MUX **/
        ret=seekAndMux(timeslots,seekCount);
    }
    if (ret)
        av_write_trailer(context.ofmt_ctx);
    //_clearDecoder();        
    free(videoStream);
    free(audioStream);
    return shutDown(ret);
} 

