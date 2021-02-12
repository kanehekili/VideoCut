/*
 * MPEG/H264 muxer/cutter/trancoder
 * Copyright (c) 2018-2019 Kanehekili
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
  * Versions supported: (libavutil/version.h)
  * ffmpeg 3.4.2
  * #define LIBAVCODEC_VERSION_MAJOR  57	 	
  * #define LIBAVCODEC_VERSION_MINOR 107
  * 
  * ffmpeg 4.x
  * #define LIBAVCODEC_VERSION_MAJOR  58
  * #define LIBAVCODEC_VERSION_MINOR 18
  */
#include <libavutil/timestamp.h>
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/opt.h>
#include <libavutil/frame.h>
#include <libavutil/mathematics.h>
#include <unistd.h>
#include <sys/sysinfo.h>
#include <stdio.h>

#if (LIBAVCODEC_VERSION_MAJOR == 57)
#define FFMPEG_REGISTER 1
#endif
#if (LIBAVCODEC_VERSION_MAJOR < 57)
#error "Ffmpeg 3.4 or newer is required"
#endif 
#define max(a,b) (a>b?a:b)
#define min(a,b) (a<b?a:b)
#define round(x) ((x)>=0?(long)((x)+0.5):(long)((x)-0.5))
#define MODE_FAST 0
#define MODE_TRANSCODE 1
#define MODE_DUMP 2
#define MODE_DUMPFRAMES 3
#define MODE_SPLIT 4

#define LANG_COUNT 3

#define TYPE_VIDEO 0x4;
#define TYPE_AUDIO 0x6;

struct StreamInfo{
    int srcIndex; //Index of ifmt_ctx stream
    int dstIndex; //Index of out stream
    AVStream *outStream;
    AVStream *inStream;
    AVCodecContext *in_codec_ctx; //Decode
    AVCodecContext *out_codec_ctx; //Encode
	double_t deltaDTS;//Time diff from one frame to another.
	int64_t frame_nbr; //count the frame number, since stream->nb_frames fails...
	int type; //either video or audio
	char *lang;
    short isTransportStream;
};

typedef struct {
    
    AVFormatContext *ifmt_ctx;
    AVFormatContext *ofmt_ctx;
    int64_t video_trail_dts;//last transcoded video dts for audio sync
	int64_t streamOffset; //the offset between audio and video stream.
	int64_t audio_sync_dts; //Sync point audio for every scene
    double_t videoLen; //Approx duration in seconds
    int isDebug;
    int muxMode;
    char* sourceFile;
    char* targetFile;
    int nprocs; //Number of (hyper)threads
    int fmtFlags;
    int *stream_mapping; //Multi audio support
    int videoIndex; //index of video in allStreams
    int refAudioIndex; //index of first audio in allStreams
} SourceContext;

typedef struct {
    int64_t start;
    int64_t end;
    int64_t dts;
    int64_t pts;
} CutData;

/*** globals ****/
    //struct StreamInfo *videoStream;
    static struct StreamInfo *allStreams;
    static SourceContext context;
    static char* lang[] = { "deu", "eng", "fra" };//may be changed, but 3 is max

/*** Basic stuff ***/
int64_t ptsFromTime(double_t ts,AVRational time_base){
    int64_t res = (int64_t)(ts*time_base.den/time_base.num);
    return res;
}
/*
static double get_fps(AVCodecContext *avctx) { //correct!
    return 1.0 / av_q2d(avctx->time_base) / FFMAX(avctx->ticks_per_frame, 1);
}
*/

static struct StreamInfo* getAudioRef(){
	return &allStreams[context.refAudioIndex];
}

static struct StreamInfo* getVideoRef(){
	return &allStreams[context.videoIndex];
}

static struct StreamInfo* getStream(int stream_index){
	int indx = context.stream_mapping[stream_index];
	if (indx<0)
		return NULL;
	return &allStreams[indx];
}

static int getLanguageIndex(char *aLang){
	int i;
	for (i = 0; i < 3; i++) {
		if (strcmp(aLang,lang[i])==0)
			return i;
	}
	return -1;
}
static int findBestVideoStream(){//enum AVMediaType type
	struct StreamInfo *info = &allStreams[0];
    int srcIndex = av_find_best_stream(context.ifmt_ctx,AVMEDIA_TYPE_VIDEO,-1,-1,NULL,0);
    if (srcIndex < 0){
    	return -1;
    }
    info->inStream=context.ifmt_ctx->streams[srcIndex];
    (&context)->stream_mapping[srcIndex]=0;
    info->srcIndex =srcIndex;
    info->type=TYPE_VIDEO;
    info->frame_nbr=0;
    context.videoIndex=0;

    const char* MPEG_TS_ID = "mpegts";
    const char* test = context.ifmt_ctx->iformat->name;
    info->isTransportStream = strcmp(test,MPEG_TS_ID) == 0 ;

    return info->srcIndex;
}

static int _collectAllStreams(){
	AVFormatContext *ifmt_ctx = context.ifmt_ctx;
	AVDictionaryEntry *currLang;
	int audioData[]={0,0,0};
	int audioCount=1;
	int videoCount=0;
	int bestAudio=0;
	context.refAudioIndex=1;
	int ret;
	for (int i = 0; i < ifmt_ctx->nb_streams; i++){
    	AVStream *stream = ifmt_ctx->streams[i];
    	context.stream_mapping[i]=-1;
    	AVCodecParameters *in_codecpar = stream->codecpar;
    	if (in_codecpar->codec_type == AVMEDIA_TYPE_VIDEO && !videoCount){
    		videoCount++;
    	    if ((ret = findBestVideoStream()) < 0) {
    	        av_log(NULL, AV_LOG_ERROR,"Err: No video stream found \n");
    	        return -1;
    	    }
    	}else if (in_codecpar->codec_type == AVMEDIA_TYPE_AUDIO){
           	int channels = in_codecpar->channels;
            int sr = in_codecpar->sample_rate;
        	currLang = av_dict_get(ifmt_ctx->streams[i]->metadata, "language", NULL,0);
        	int audioIndex= currLang!=NULL?getLanguageIndex(currLang->value):-1;
        	if (audioIndex != -1 && channels && sr && !audioData[audioIndex]){
        		int targetStreamIndex=audioIndex+1;
        		struct StreamInfo *info = &allStreams[targetStreamIndex];
        		info->srcIndex=i;
        		info->inStream=ifmt_ctx->streams[i];
        		info->type=TYPE_AUDIO;
        		info->lang=currLang->value;
        		info->frame_nbr=0;
        	    audioData[audioIndex]=channels*100000+sr;
        	    if (bestAudio < audioData[audioIndex]){
        	    	bestAudio = audioData[audioIndex];
        	    	context.refAudioIndex=targetStreamIndex;
        	    }
        	    (&context)->stream_mapping[i]=targetStreamIndex;
            	audioCount++;
        	}
        }
	}
	if (audioCount==1){
		struct StreamInfo *info = &allStreams[1];
		info->srcIndex = av_find_best_stream(context.ifmt_ctx,AVMEDIA_TYPE_AUDIO,-1,-1,NULL,0);
		if (AVERROR_STREAM_NOT_FOUND == info->srcIndex){
			av_log(NULL, AV_LOG_INFO,"No audio stream found \n");
			return -1;
		}
		currLang = av_dict_get(ifmt_ctx->streams[info->srcIndex]->metadata, "language", NULL,0);
		info->inStream=context.ifmt_ctx->streams[info->srcIndex];
		info->dstIndex=1;
		info->type=TYPE_AUDIO;
		if (currLang)
			info->lang=currLang->value;
		context.stream_mapping[info->srcIndex]=1;
	}
	return 1;
}

static AVOutputFormat* checkVideoFormat(struct StreamInfo *info,char *out_filename){
	AVOutputFormat *ofmt = NULL;
   int codecID = info->inStream->codecpar->codec_id;
   if (codecID == AV_CODEC_ID_MPEG2VIDEO){
	   ofmt= av_guess_format(NULL,out_filename, NULL);
	   if (ofmt->video_codec == AV_CODEC_ID_MPEG1VIDEO)
		   ofmt= av_guess_format("dvd", NULL, NULL);
        av_log(NULL, AV_LOG_INFO,"MPEG2 set to PS-stream\n");
    }else if(codecID == AV_CODEC_ID_VC1){
    	context.fmtFlags |= AVFMT_NOTIMESTAMPS;
    	if (context.muxMode==MODE_TRANSCODE){//VC-1 - we can't encode that
    		ofmt= av_guess_format("mp4", NULL, NULL);//libavcodec dosn't support mkv (vorbis seems to be the problem)
    	    av_log(NULL, AV_LOG_INFO,"Matroska/VC1 set to mp4\n");
    	}
    }else if ((codecID == AV_CODEC_ID_VP8 || codecID == AV_CODEC_ID_VP9) && context.muxMode==MODE_TRANSCODE){
    	ofmt= av_guess_format("webm", NULL, NULL);
    	ofmt->video_codec = AV_CODEC_ID_VP8;
    }
   //Example to force the input codec - which may not be the favorite for the container.
   //ofmt= av_guess_format(NULL,out_filename, NULL);
   //ofmt->video_codec = codecID;
    return ofmt;
}
/*
static void logXtraData(AVCodecParameters *inCodecParm){
	int cnt = inCodecParm->extradata_size;
	int i=0;
	for (i=0; i<cnt; i++) {
		uint8_t dta = inCodecParm->extradata[i];
		av_log(NULL, AV_LOG_VERBOSE,"0x%02x,",dta);
	}
	av_log(NULL, AV_LOG_VERBOSE,"\n");
}
*/
/*
static void generateXtraData(AVCodecParameters *outCodecParm){
    //length of extradata is 6 bytes + 2 bytes for spslen + sps + 1 byte number of pps + 2 bytes for ppslen + pps
	 uint8_t pps[]={0x27,0x64,0x00,0x28,0xac,0x2b,0x40,0xa0,0xcd,0x00,0xf1,0x22,0x6a};
	 uint8_t sps[]={0x28,0xee,0x04,0xf2,0xc0};
	 int spslen=sizeof(sps);
	 int ppslen=sizeof(pps);
     uint32_t extradata_len = 8 + spslen + 1 + 2 + ppslen;
     outCodecParm->extradata = (uint8_t*)av_mallocz(extradata_len);

     outCodecParm->extradata_size = extradata_len;

     //start writing avcc extradata
     outCodecParm->extradata[0] = 0x01;      //version
     outCodecParm->extradata[1] = sps[1];    //profile
     outCodecParm->extradata[2] = sps[2];    //comatibility
     outCodecParm->extradata[3] = sps[3];    //level
     outCodecParm->extradata[4] = 0xFC | 3;  // reserved (6 bits), NALU length size - 1 (2 bits) which is 3
     outCodecParm->extradata[5] = 0xE0 | 1;  // reserved (3 bits), num of SPS (5 bits) which is 1 sps

     //write sps length
     memcpy(&outCodecParm->extradata[6],&spslen,2);

     //Check to see if written correctly
     uint16_t *cspslen=(uint16_t *)&outCodecParm->extradata[6];
     fprintf(stderr,"SPS length Wrote %d and read %d \n",spslen,*cspslen);


     //Write the actual sps
     int i = 0;
     for (i=0; i<spslen; i++) {
       outCodecParm->extradata[8 + i] = sps[i];
     }

     for (size_t i = 0; i != outCodecParm->extradata_size; ++i){
           fprintf(stderr, "\\%02x", (unsigned char)outCodecParm->extradata[i]);
     }
     fprintf(stderr,"\n");
     //Number of pps
     outCodecParm->extradata[8 + spslen] = 0x01;

     //Size of pps
     memcpy(&outCodecParm->extradata[8+spslen+1],&ppslen,2);

     for (size_t i = 0; i != outCodecParm->extradata_size; ++i){
           fprintf(stderr, "\\%02x", (unsigned char)outCodecParm->extradata[i]);
     }
     fprintf(stderr,"\n");
     //Check to see if written correctly
     uint16_t *cppslen=(uint16_t *)&outCodecParm->extradata[+8+spslen+1];
     fprintf(stderr,"PPS length Wrote %d and read %d \n",ppslen,*cppslen);


     //Write actual PPS
     for (i=0; i<ppslen; i++) {
      outCodecParm->extradata[8 + spslen + 1 + 2 + i] = pps[i];
     }

     //Output the extradata to check
     for (size_t i = 0; i != outCodecParm->extradata_size; ++i){
           fprintf(stderr, "\\%02x", (unsigned char)outCodecParm->extradata[i]);
     }
     fprintf(stderr,"\n");
}
*/

static void setupOutputParamters(struct StreamInfo *info, AVStream *outStream){
	AVCodecParameters *inCodecParm = info->inStream->codecpar;
	AVCodecParameters *outCodecParm = outStream->codecpar;

	//works with vc-1 to h264, but not with vp8/av1 to h264...
	outCodecParm->codec_type=inCodecParm->codec_type;
	outCodecParm->codec_id = context.ofmt_ctx->oformat->video_codec;
	outCodecParm->codec_tag =0;
	outCodecParm->width=inCodecParm->width;
	outCodecParm->height=inCodecParm->height;
	outCodecParm->field_order = inCodecParm->field_order;
	outCodecParm->color_primaries = inCodecParm->color_primaries;
	outCodecParm->color_range= inCodecParm->color_range;
	outCodecParm->color_space = inCodecParm->color_space;
	outCodecParm->color_trc = inCodecParm->color_trc;
	outCodecParm->bit_rate = context.ifmt_ctx->bit_rate;
	outCodecParm->bits_per_coded_sample = inCodecParm->bits_per_coded_sample;

	/*meta data test
	 AVDictionaryEntry *tag = NULL;
	while ((tag = av_dict_get(context.ifmt_ctx->metadata, "", tag, AV_DICT_IGNORE_SUFFIX)))
		printf("in: %s=%s\n", tag->key, tag->value);

	while ((tag = av_dict_get(context.ofmt_ctx->metadata, "", tag, AV_DICT_IGNORE_SUFFIX)))
		printf("out: %s=%s\n", tag->key, tag->value);
	 */
	//missing?
//	outCodecParm->format = 0; //pix_fmt AVPixelFormat pix_fmt = video_dec_ctx->pix_fmt;
//	outCodecParm->video_delay = 0;// codec->has_b_frames;
//	outCodecParm->bits_per_raw_sample=0;
//	outCodecParm->profile=0;
	//breaks mkv to h264: outCodecParm->level=inCodecParm->level;
	//missing and important!
	outCodecParm->format = info->in_codec_ctx->pix_fmt;
}

static int createOutputStream(struct StreamInfo *info){
    AVStream *out_stream;
    AVCodecParameters *pCodecParm = info->inStream->codecpar;

    out_stream = avformat_new_stream(context.ofmt_ctx, NULL);
    if (!out_stream) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed allocating output stream\n");
        return AVERROR_UNKNOWN;
    }

    /**
     * If the video codecs change (VC1 to h264), then parameter copy will not work (extradata must be updated)
     */
    short sameCodec = (info->inStream->codecpar->codec_id == context.ofmt_ctx->oformat->video_codec);
    if (!sameCodec && pCodecParm->codec_type==AVMEDIA_TYPE_VIDEO && context.muxMode==MODE_TRANSCODE){
    	av_log(NULL, AV_LOG_INFO,"Set output params manually\n");
    	setupOutputParamters(info,out_stream);
    }else {
		//Copy of stream params in case of same codec
		int ret = avcodec_parameters_copy(out_stream->codecpar, pCodecParm);
		if (ret < 0) {
			av_log(NULL, AV_LOG_ERROR,"Err: Failed to copy codec parameters\n");
			return ret;
		}
		out_stream->codecpar->codec_tag = 0;//if not m2t to mp4 fails

    }
    out_stream->start_time=AV_NOPTS_VALUE;
    out_stream->duration=0;
    out_stream->avg_frame_rate = info->inStream->avg_frame_rate;
    
    if (pCodecParm->codec_type==AVMEDIA_TYPE_AUDIO){
        out_stream->codecpar->frame_size = av_get_audio_frame_duration2(pCodecParm,0);
    }
    info->outStream=out_stream;
    return 1;
}

/*
 * Copies the sidedata - currently the rotation information
 */
int _copySidedata(struct StreamInfo *info){
    uint8_t *data;
    int size;
	data = av_stream_get_side_data(info->inStream,AV_PKT_DATA_DISPLAYMATRIX, &size);
	if (data && size >= 9 * sizeof(int32_t)) {
       av_log(NULL, AV_LOG_VERBOSE,"displaymatrix copied \n");
       av_stream_add_side_data(info->outStream,AV_PKT_DATA_DISPLAYMATRIX,data,size);
	}
    return 1;
}

int _initOutputContext(AVOutputFormat *pre_ofmt, char *out_filename){
	struct StreamInfo *videoInfo = getVideoRef();
    AVFormatContext *ofmt_ctx = NULL; 
    AVOutputFormat *ofmt = NULL;
    int destIndx=0;
    int ret;
    
    ret= avformat_alloc_output_context2(&ofmt_ctx, pre_ofmt, NULL, out_filename);
    if (!ofmt_ctx || ret < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Could not create output context\n");
        return -1;
    }
 
    context.ofmt_ctx = ofmt_ctx;
    ofmt = ofmt_ctx->oformat;

    if ((ret = createOutputStream(videoInfo))< 0){
        av_log(NULL, AV_LOG_ERROR,"Err: Could not create video output \n");
        return -1;
    }
    videoInfo->dstIndex = destIndx++;
    int64_t bitrate = context.ifmt_ctx->bit_rate;
    av_log(NULL, AV_LOG_INFO,"Video bitrate: %ld \n",bitrate);
    ofmt_ctx->bit_rate = bitrate;//avg bitrate,just an indicator..

    /* The VBV Buffer warning is removed: */
    AVCPBProperties *props;
    props = (AVCPBProperties*) av_stream_new_side_data(videoInfo->outStream, AV_PKT_DATA_CPB_PROPERTIES, sizeof(*props));

    props->buffer_size = 2024 *1024;
    props->max_bitrate = 15*bitrate;//Lower means buffer underflow & pixelation during cut
    props->min_bitrate = (2*bitrate)/3;
    props->avg_bitrate = bitrate;
    props->vbv_delay = UINT64_MAX;


    for (int i = 0; i < LANG_COUNT; ++i) {
		struct StreamInfo *audioStream = &allStreams[i+1];
		if (!audioStream->inStream)
			continue;
        if ((ret = createOutputStream(audioStream))< 0){
            av_log(NULL, AV_LOG_ERROR,"Err: Could not create video output \n");
            return -1;
        }
        audioStream->dstIndex = destIndx++;
        if (audioStream->lang){
			AVDictionary *meta = NULL;
			ret = av_dict_set(&meta,"language",audioStream->lang,0);
	        audioStream->outStream->metadata = meta;
        }
		int sampleRate = audioStream->inStream->codecpar->sample_rate;
		bitrate = audioStream->inStream->codecpar->bit_rate;
		av_log(NULL, AV_LOG_INFO,"Audio: sample rate: %d bitrate: %ld\n",sampleRate,bitrate);
     }

    _copySidedata(videoInfo);

    av_dump_format(ofmt_ctx, 0, out_filename, 1);

    if (!(ofmt->flags & AVFMT_NOFILE)) {
        ret = avio_open(&ofmt_ctx->pb, out_filename, AVIO_FLAG_WRITE);
        if (ret < 0) {
            av_log(NULL, AV_LOG_ERROR,"Err: Could not open output file '%s'\n", out_filename);
            return -1;
        }
     }

    //timebase will be set AFTER this call,av1 codec will fail (and some more mkv codecs)
    ret = avformat_write_header(ofmt_ctx, NULL);
    if (ret < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Write header: %s\n", av_err2str(ret));
        return -1;
    }
    //breaks: videoStream->outStream->time_base= av_guess_frame_rate(context.ofmt_ctx,videoStream->inStream,NULL);
    return 1;
}

static int _initDecoder(struct StreamInfo *info){
    AVCodec *dec = NULL;
    AVCodecContext *dec_ctx = NULL;
    AVDictionary *opts = NULL;
    
    int ret;
    dec = avcodec_find_decoder(info->inStream->codecpar->codec_id);
    if (!dec) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed to find %s codec\n",av_get_media_type_string(AVMEDIA_TYPE_VIDEO));
        return -1;
    } 
    
    /* Allocate a codec context for the decoder */
    dec_ctx = avcodec_alloc_context3(dec);
    if (dec_ctx == NULL){
       av_log(NULL, AV_LOG_ERROR,"Err: Failed to alloc codec context\n");
       return -1;
    }
    avcodec_parameters_to_context(dec_ctx, info->inStream->codecpar);
    av_dict_set(&opts, "refcounted_frames","1",0);
    dec_ctx->framerate = av_guess_frame_rate(context.ifmt_ctx, info->inStream, NULL);
    //configure multi threading
    dec_ctx->thread_count=context.nprocs;
    dec_ctx->thread_type = FF_THREAD_FRAME | FF_THREAD_SLICE;
    //dec_ctx->thread_type = FF_THREAD_SLICE;
    av_log(NULL,AV_LOG_INFO,"Registered %d decoding threads \n",dec_ctx->thread_count);
    if ((ret=avcodec_open2(dec_ctx,dec,&opts))<0){ 
       av_log(NULL, AV_LOG_ERROR,"Err: Failed to open codec context\n");
       return -1;
    }
    info->in_codec_ctx=dec_ctx;
    info->out_codec_ctx=NULL;
    return 1;
}

static int _initEncoder(struct StreamInfo *info, AVFrame *frame){
    AVCodec *encoder = NULL;
    AVCodecContext *enc_ctx = NULL;
    AVCodecContext *dec_ctx = NULL;
    AVDictionary *opts = NULL;
    int ret;
    encoder=avcodec_find_encoder(context.ofmt_ctx->oformat->video_codec);
    if (!encoder) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed to find %s out en-codec\n",av_get_media_type_string(AVMEDIA_TYPE_VIDEO));
        return -1;
    } 

    dec_ctx = info->in_codec_ctx;

    /* Allocate a codec context for the encoder - the dta should come from stream, not dec_ctx*/
    enc_ctx = avcodec_alloc_context3(encoder);
    if (enc_ctx == NULL){
       av_log(NULL, AV_LOG_ERROR,"Err: Failed to alloc out en-codec context\n");
       return -1;
    }
    //Most of the parameters should not be changed... No effect or even distortion.
    avcodec_parameters_to_context(enc_ctx,info->outStream->codecpar);
//    enc_ctx->height = dec_ctx->height;
//    enc_ctx->width = dec_ctx->width;
//    enc_ctx->bit_rate = context.ifmt_ctx->bit_rate;
    enc_ctx->sample_aspect_ratio = dec_ctx->sample_aspect_ratio;

    // take first format from list of supported formats 
    if (encoder->pix_fmts)
        enc_ctx->pix_fmt = encoder->pix_fmts[0];
    else
        enc_ctx->pix_fmt = dec_ctx->pix_fmt;
    // video time_base can be set to whatever is handy and supported by encoder !MUST!
    /*Setting of TB alters the bitrate:
     * 1/framerate: 39 mb
     * framerate 1001/24000
     * 1:90000 -> 1200 kb
     * 1:1000 ->3000 kb
     */

    enc_ctx->time_base = av_inv_q(dec_ctx->framerate);
    enc_ctx->framerate = dec_ctx->framerate;
    enc_ctx->max_b_frames = 4;
	if (encoder->id == AV_CODEC_ID_H264){
     	enc_ctx->ticks_per_frame=dec_ctx->ticks_per_frame;//should be 2!
     	//crf has no big impact on bitrate, 18 has hardly an effect on avc to avc, but increases bitrate from mp2 to mp4...
		av_opt_set(enc_ctx->priv_data, "crf","18",0);
		//profile: baseline, main, high, high10, high422, high444
		av_opt_set(enc_ctx->priv_data, "profile", "high", 0);//more devices..
		av_opt_set(enc_ctx->priv_data, "preset", "medium", 0);
		//av_dict_set(&opts, "movflags", "faststart", 0);
		//Bitrate section h264 -> if max then buffer -< but not reliably working with this codec!
		//enc_ctx->bit_rate = context.ifmt_ctx->bit_rate; ->copy params
		enc_ctx->rc_max_rate = context.ifmt_ctx->bit_rate;
		enc_ctx->rc_min_rate = (context.ifmt_ctx->bit_rate)/3;
		/*Basically, if you plan on encoding with CBR, you should limit the buffer to one second.
		 * That means the size = bitrate*seconds to buffer.
		 * The lower the buffer, the less the rate variance.
		 * https://streaminglearningcenter.com/blogs/book-excerpt-vbv-buffer-explained.html
		 * The VC1 decoder is broken ....
		 */
		if (dec_ctx->codec_id != AV_CODEC_ID_VC1){
			enc_ctx->rc_buffer_size= (int)(enc_ctx->rc_max_rate);
			//The lower the more bitrate.... Make it configurable!
			enc_ctx->qmin = 1;
			enc_ctx->qmax = 18;//18 increase bitrate from mp2 to mp4.. no effect on mkv to mp4...
		}else {
			enc_ctx->rc_buffer_size= (int)(enc_ctx->rc_max_rate);
			enc_ctx->qmin = 18;
			enc_ctx->qmax = 23;
		}

     } else if (encoder->id == AV_CODEC_ID_MPEG2VIDEO){
        //enc_ctx->max_b_frames = 2;
        enc_ctx->bit_rate = context.ifmt_ctx->bit_rate;
        enc_ctx->ticks_per_frame=2;

    }
	//In case of experimental encoder
	//av_dict_set(&opts, "strict", "experimental", 0);
    //configure multi threading
    enc_ctx->thread_count=context.nprocs;
    enc_ctx->thread_type = FF_THREAD_FRAME | FF_THREAD_SLICE;
    av_log(NULL,AV_LOG_INFO,"Registered %d encoding threads \n",enc_ctx->thread_count);
    if ((ret=avcodec_open2(enc_ctx,encoder,&opts))<0){ 
       av_log(NULL, AV_LOG_ERROR,"Err: Failed to open en-codec context\n");
       return -1;
    }

    //Despite other examples: flags MUST be set after open2
    ret = avcodec_parameters_from_context(info->outStream->codecpar, enc_ctx);
    if (ret < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed to copy encoder parameters to output stream \n");
        return ret;
    }   

    if (context.ofmt_ctx->oformat->flags & AVFMT_GLOBALHEADER){
        av_log(NULL, AV_LOG_INFO,"Using GLOBAL encode headers\n");
        enc_ctx->flags |= AV_CODEC_FLAG_GLOBAL_HEADER; 
    }

    if (context.ofmt_ctx->oformat->flags & AVFMT_VARIABLE_FPS){
    	av_log(NULL, AV_LOG_INFO,"Detected VAR FPS\n");
    	enc_ctx->flags |= AVFMT_VARIABLE_FPS;
    }

    frame->format = info->in_codec_ctx->pix_fmt;
    frame->width = info->in_codec_ctx->width;
    frame->height = info->in_codec_ctx->height;

    info->out_codec_ctx=enc_ctx;
    return 1;
}

int _setupStreams(SourceContext *sctx ){
    int ret;
    AVFormatContext *ifmt_ctx = NULL;
    char *in_filename = sctx->sourceFile;
    char *out_filename = sctx->targetFile;


    #ifdef FFMPEG_REGISTER
        av_register_all();
    #endif

    if ((ret = avformat_open_input(&ifmt_ctx, in_filename, 0, 0)) < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Could not open input file '%s'\n", in_filename);
        return -1;
    }

    if ((ret = avformat_find_stream_info(ifmt_ctx,NULL)) < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed to retrieve input stream information\n");
        return -1;
    }

    av_dump_format(ifmt_ctx, 0, in_filename, 0);

    context.ifmt_ctx = ifmt_ctx;
    //context.ifmt_ctx->flags |= AVFMT_FLAG_GENPTS;//BREAKS PTS
    int stream_mapping_size = ifmt_ctx->nb_streams;
    context.stream_mapping = av_mallocz_array(stream_mapping_size, sizeof(context.stream_mapping));


    //Later we take all audio streams.

    if ((ret = _collectAllStreams()) < 0)
      av_log(NULL, AV_LOG_INFO,"Streams missing\n");


    if (getVideoRef()->srcIndex>=0){
    	_initDecoder(getVideoRef());
    	AVOutputFormat *preFormat = checkVideoFormat(getVideoRef(),out_filename);
    	return _initOutputContext(preFormat,out_filename);
    }
    return -1;
}


/**************** MUXING SECTION ***********************/
//TODO: Tail should be always BEFORE or AT the cut point
static int seekTailGOP(struct StreamInfo *info, int64_t ts,CutData *borders) {
    AVPacket pkt;
    int64_t lookback=ptsFromTime(10.0,info->inStream->time_base); //go 10 seconds back in time
    int timeHit=0;
    int keyFrameCount=0;
    int maxFrames=3;
    int64_t gop[3]={0,0,0};

    if (lookback > ts)
        lookback=0;
     av_init_packet(&pkt);
    if(av_seek_frame(context.ifmt_ctx, info->srcIndex, ts-lookback, AVSEEK_FLAG_BACKWARD) < 0){
        av_log(NULL, AV_LOG_ERROR,"Err: av_seek_frame failed.\n");
        return -1;
    }
   
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
       if (pkt.stream_index != info->srcIndex){
            av_packet_unref(&pkt); 
            continue;
        }    
        int i;
        if (pkt.flags == AV_PKT_FLAG_KEY){
            for (i =0; i< maxFrames-1; i++){
                gop[i]=gop[i+1];
            }
            gop[maxFrames-1]=pkt.dts;
            keyFrameCount++;
            if (timeHit)
                break;
        } 
        if (pkt.dts >= ts && !timeHit){
            timeHit=1;
            borders->dts=pkt.dts;
            borders->pts=pkt.pts;
        }
        av_packet_unref(&pkt); 
    }

    av_packet_unref(&pkt); 
    int idx=0;
    int t1 = abs(ts - gop[1]);
    int t2 = abs(ts - gop[2]);
    if (t1 > t2){
        idx++;
    }
    borders->start=gop[idx];
    //h264 non TS precise cut:
    short isTS = info->isTransportStream;
    short isMP4 = info->in_codec_ctx->codec_id==AV_CODEC_ID_H264;
	if (isMP4 && !isTS)
		borders->end=borders->dts;
	else
		borders->end=gop[idx+1];
    AVRational time_base = info->inStream->time_base;
    int64_t vStreamOffset = info->inStream->start_time;    
    double_t st = av_q2d(time_base)*(ts-vStreamOffset);
    double_t g0 = av_q2d(time_base)*(gop[idx]-vStreamOffset);
    double_t g1 = av_q2d(time_base)*(gop[idx+1]-vStreamOffset);
    av_log(NULL, AV_LOG_VERBOSE,"Tail: (keycount %d block: %d) deltas: %d/%d Searchkey:%ld (%.3f) Start:%ld (%.3f) > End: %ld (%.3f) (cutpoint dts:%ld)",keyFrameCount,idx,t1,t2,ts,st,borders->start,g0,borders->end,g1,borders->dts);
    if (borders->pts != AV_NOPTS_VALUE)
    	av_log(NULL, AV_LOG_VERBOSE,"pts %ld\n",borders->pts);
    else
    	av_log(NULL, AV_LOG_VERBOSE,"\n");
    return 1;

}

//seeking only the video stream head
////TODO: Head should be always AFTER or AT the cut point
static int seekHeadGOP(struct StreamInfo *info, int64_t ts,CutData *borders) {
    AVPacket pkt;
    int64_t lookback=ptsFromTime(1.0,info->inStream->time_base);
    int timeHit=0;
    int keyFrameCount=0;
    int gopIndx=0;
    int maxFrames=3;
    int64_t gop[3]={0,0,0};

    if (lookback > ts)
        lookback=ts;
    //const int genPts= context.ifmt_ctx->flags & AVFMT_FLAG_GENPTS; alway 0->so packet buffer is used
    av_init_packet(&pkt);
    if(av_seek_frame(context.ifmt_ctx, info->srcIndex, ts-lookback, AVSEEK_FLAG_BACKWARD) < 0){
        av_log(NULL, AV_LOG_ERROR,"Err: av_seek_frame failed.\n");
        return -1;
    }
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
       if (pkt.stream_index != info->srcIndex){
            av_packet_unref(&pkt); 
            continue;
        }    
        if (pkt.flags == AV_PKT_FLAG_KEY && pkt.dts != AV_NOPTS_VALUE){
            if (timeHit)
            	gopIndx++;
            gop[gopIndx]=pkt.dts;
            keyFrameCount++; 
            if (gopIndx==maxFrames-1)//one gop == 2 frames are needed
                break;
        } 
        
        if (pkt.dts >= ts && !timeHit){
            timeHit=1;
            borders->dts=pkt.dts;
            borders->pts=pkt.pts;
        }
        av_packet_unref(&pkt); 
    }

    av_packet_unref(&pkt); 
    int idx=0;
	int t1 = abs(ts - gop[0]);
	int t2 = abs(ts - gop[1]);
    if (context.muxMode != MODE_TRANSCODE && t2 < t1){
			idx++;
    }
    borders->start=gop[idx];
    borders->end=gop[idx+1];
    AVRational time_base = info->inStream->time_base;
    int64_t vStreamOffset = info->inStream->start_time;
    double_t st = av_q2d(time_base)*(ts-vStreamOffset);
    double_t g0 = av_q2d(time_base)*(gop[idx]-vStreamOffset);
    double_t g1 = av_q2d(time_base)*(gop[idx+1]-vStreamOffset);
    av_log(NULL, AV_LOG_VERBOSE,"Head:(keycount %d block: %d) deltas: %d/%d Searchkey:%ld (%.3f) start:%ld (%.3f) > End: %ld (%.3f) (cutpoint-dts:%ld) \n",keyFrameCount,idx,t1,t2,ts,st,borders->start,g0,borders->end,g1,borders->dts);
    return keyFrameCount<4;
}
/** Write packet to the out put stream. Here we calculate the PTS/dts. Only Audio and video streams are incoming  **/
static int write_packet(struct StreamInfo *info,AVPacket *pkt){
        AVStream *in_stream = NULL, *out_stream = NULL;
        struct StreamInfo *audioRef = getAudioRef();
        struct StreamInfo *videoRef = getVideoRef();
        int64_t syncOffset=0.0;
        char frm='*';
        int isVideo = videoRef->srcIndex==pkt->stream_index;

        if (isVideo) {
            //context.frame_number+=1;
            if (pkt->flags == AV_PKT_FLAG_KEY){
              frm='I';
            }
            else
                frm='v';      
        }
        in_stream  = info->inStream;
        out_stream  = info->outStream;

        /**
         * Cutting data is in video time. Convert it from video time to stream time.
        */ 
        int64_t currentDTS = info->outStream->cur_dts; //out-time

        //remove early audio packets.... crucial!
        if (!isVideo && (pkt->dts < context.audio_sync_dts)){
            double_t currTS = av_q2d(out_stream->time_base)*context.audio_sync_dts;
            double_t audioTS = av_q2d(out_stream->time_base)*pkt->dts;
			av_log(NULL, AV_LOG_VERBOSE,"Drop early packet: %c: dts:%ld (%.3f) synctime (%.3f)\n",frm,pkt->dts,audioTS,currTS);
			av_packet_unref(pkt);
			return 1;
		}

//        if (currentDTS == AV_NOPTS_VALUE ){
//        }
        /* save original packet dates*/
        int64_t p1 = pkt->pts;
        int64_t d1 = pkt->dts;
        int64_t delta = p1-d1;
        int64_t dur = pkt->duration;

        pkt->stream_index = info->dstIndex;
        pkt->pos=-1;//File pos is unknown if cut..

        //remux workaround ... duration may be 0 ->next pts - curr pts... will not work if pts invalid
        //dur=0  always on transcoding. isTimeless: On timeless vc1 codec..
        short isTimeless = context.fmtFlags & AVFMT_NOTIMESTAMPS;
        if ((dur==0 || isTimeless) && isVideo){
		   //pkt->dts = (int64_t)(info->frame_nbr*info->deltaDTS);
		   //pkt->duration = pkt->dts - currentDTS;
        	if (currentDTS == AV_NOPTS_VALUE){
        		pkt->dts = syncOffset;
        		currentDTS =syncOffset;
        	}
        	else{
        		pkt->dts = currentDTS+(int64_t)info->deltaDTS;
        	}
		   pkt->duration = (int64_t)info->deltaDTS;
		   context.video_trail_dts=pkt->dts;//needed by trailing audio
        }else {
        	pkt->duration = av_rescale_q(dur, in_stream->time_base, out_stream->time_base);
			//increment the DTS instead of calculating it.
        	if (currentDTS == AV_NOPTS_VALUE){
        		pkt->dts = syncOffset;
        		currentDTS =syncOffset;
        	}
       		else
       			pkt->dts = currentDTS+pkt->duration;
        }

        //PTS calculation
        if (isVideo && isTimeless)
        	   pkt->pts=pkt->dts;
        else if (p1 != AV_NOPTS_VALUE)
		   pkt->pts = pkt->dts+delta;

        double_t dtsCalcTime = av_q2d(out_stream->time_base)*(pkt->dts);
        int ts = (int)dtsCalcTime;
        int hr = (ts/3600);
        int min =(ts%3600)/60;
        int sec = (ts%60)%60;  
        
        if (isVideo && !context.isDebug){
            double_t progress = (dtsCalcTime/context.videoLen)*100;
            av_log(NULL, AV_LOG_INFO,"%ld D:%.2f %02d:%02d.%02d %.2f%%\n",info->frame_nbr,dtsCalcTime,hr,min,sec,progress);
        }
        if (context.isDebug && (pkt->stream_index<2)){
            double_t ptsCalcTime = av_q2d(out_stream->time_base)*(pkt->pts);
            double_t orgDTSTime= av_q2d(in_stream->time_base)*(d1);
            double_t orgPTSTime = av_q2d(in_stream->time_base)*(p1);
            char other=isVideo?'A':'V';
			AVRational audioInTB = {1,1};
            if (audioRef->inStream){
            	audioInTB=audioRef->inStream->time_base;
            }
            int64_t cv = isVideo? av_rescale_q(d1,info->inStream->time_base,audioInTB):av_rescale_q(d1,info->inStream->time_base,videoRef->inStream->time_base);
            if (p1==AV_NOPTS_VALUE){
            	av_log(NULL, AV_LOG_VERBOSE,"%ld,%c:P:NONE", info->frame_nbr,frm);
            } else{
            	av_log(NULL, AV_LOG_VERBOSE,"%ld,%c:P:%ld (%ld-%.3f)",info->frame_nbr,frm,pkt->pts,p1,orgPTSTime);
            }
        	av_log(NULL, AV_LOG_VERBOSE," D:%ld (%ld %c:%ld T:%.3f) Pt:%.3f Dt:%.3f dur %ld (%ld) delta: %ld size: %d curr:%ld\n",pkt->dts,d1,other,cv,orgDTSTime,ptsCalcTime,dtsCalcTime,pkt->duration,dur,delta,pkt->size,currentDTS);
        }
        int ret = av_interleaved_write_frame(context.ofmt_ctx, pkt);
        if (ret < 0) {
            av_log(NULL, AV_LOG_ERROR,"Err: Error muxing packet\n");
            return ret;
        }
        info->frame_nbr++;//Only if really written
        av_packet_unref(pkt);
        return 1;
        
}

//Plain muxing, no encoding.Expect an Iframe first
static int mux1(CutData head,CutData tail){
    struct StreamInfo *streamInfo;
    AVPacket pkt = { .data = NULL, .size = 0 };
    struct StreamInfo *audioref = getAudioRef();
    struct StreamInfo *videoStream = getVideoRef();
    int fcnt =0;
    av_init_packet(&pkt);
    int64_t audioTail = audioref->inStream? av_rescale_q(tail.end,videoStream->inStream->time_base, audioref->inStream->time_base):0;
    short audioAtEnd = audioTail==0;
    short videoAtEnd = 0;
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
        streamInfo = getStream(pkt.stream_index);
        if (!streamInfo){
            av_packet_unref(&pkt);
            continue; //No usable packet.
        }
        int isVideo = streamInfo->type==TYPE_VIDEO;
        if (isVideo){
            char frm='v';
            if (pkt.flags == AV_PKT_FLAG_KEY && pkt.dts >=head.start){
                fcnt=1;
                frm='I';
            }
            if (pkt.dts==AV_NOPTS_VALUE)
            	pkt.dts = pkt.pts-42; //what else ;-)
            //ignore leading and trailing video packets. 
            if (fcnt==0 ){
                av_log(NULL,AV_LOG_VERBOSE,"Skip head packet %ld [%c]\n",pkt.dts,frm);
                av_packet_unref(&pkt);
                continue;
            }
            if (pkt.dts >=tail.end){
              if (audioAtEnd)
                 break;
               else {
                if (pkt.flags == AV_PKT_FLAG_KEY && !videoAtEnd && streamInfo->in_codec_ctx->codec_id==AV_CODEC_ID_MPEG2VIDEO){
                	write_packet(streamInfo,&pkt);
                }
                else {
                	av_log(NULL,AV_LOG_VERBOSE,"Skip tail packet %ld [%c]\n",pkt.dts,frm);
                	av_packet_unref(&pkt);
                }
                videoAtEnd=1;
                continue;
               }
            }
              
        } else {
            //run audio until it reaches tail.end as well
            if (pkt.dts >= audioTail){
                if (videoAtEnd)
                  break;
                else {
                av_packet_unref(&pkt);
                av_log(NULL,AV_LOG_VERBOSE,"Skip tail packet %ld [*]\n",pkt.dts);
                audioAtEnd=1;
                continue;
              }
		    }
        }  

        write_packet(streamInfo,&pkt);
    }
    av_packet_unref(&pkt);
    av_interleaved_write_frame(context.ofmt_ctx, NULL);//flushing
    return 1;
}

static int decode(AVCodecContext *dec_ctx,AVPacket *pkt,AVFrame *frame){
   
    int ret = avcodec_send_packet(dec_ctx, pkt);
    if (ret < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Error sending a packet for decoding\n");
        return ret;
    }
    ret = avcodec_receive_frame(dec_ctx, frame);
    if (ret == AVERROR(EAGAIN)){ //Output not available - send a new input
        return -1;
    }
    if (ret == AVERROR_EOF){
        av_log(NULL, AV_LOG_ERROR,"Err: Error receiving a decoded frame\n");
        return -2;
    }
    return ret;
    
}

//find offset correction: Take the first I Frame

static int64_t seekPrimaryOffset(struct StreamInfo *info){
    AVPacket pkt;
    int64_t first_dts = 0;
    
     av_init_packet(&pkt);
     if(av_seek_frame(context.ifmt_ctx, info->srcIndex,0, AVSEEK_FLAG_BACKWARD) < 0){
        av_log(NULL, AV_LOG_ERROR,"Err: av_seek_frame failed.\n");
        return -1;
    }
    
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
       if (pkt.stream_index != info->srcIndex){
            av_packet_unref(&pkt); 
            continue;
        }
        if (pkt.flags == AV_PKT_FLAG_KEY ){
            first_dts = pkt.dts;
            break;
        }
        av_packet_unref(&pkt); 
    }
    av_packet_unref(&pkt); 
    
    avcodec_flush_buffers(info->in_codec_ctx);
    
    return first_dts;
}

static int flushFrames(struct StreamInfo *info, AVFrame *frame){
    int ret;
    if((ret = avcodec_send_packet(info->in_codec_ctx, NULL))>=0){
        while (ret >=0){
            ret = avcodec_receive_frame(info->in_codec_ctx,frame);
            if (ret==0){
                if (frame->flags & AV_FRAME_FLAG_DISCARD){
                    av_log(NULL,AV_LOG_INFO,"frame will be discarded: %ld\n",frame->pts);
                    continue;
                }
                int ret2;
                ret2=avcodec_send_frame(info->out_codec_ctx,frame);
                if (ret2==0){
                    av_log(NULL, AV_LOG_VERBOSE,"flush Frame sent: P:%ld dur:%ld\n",frame->pts,frame->pkt_duration);
                    AVPacket enc_pkt;
                    enc_pkt.data = NULL;
                    enc_pkt.size = 0;
                    av_init_packet(&enc_pkt);
                    int ret3 =0;
                    while (ret3 >=0){
                        ret3=avcodec_receive_packet(info->out_codec_ctx,&enc_pkt);
                        if (ret3 ==0){
                            av_log(NULL, AV_LOG_VERBOSE,"f->");
                            enc_pkt.stream_index=info->inStream->index;//compatibility
                            write_packet(info,&enc_pkt);
                        }
                    }
                }else {
                    av_log(NULL, AV_LOG_ERROR,"Err: -Frame error %d\n",ret2);
                }
            }
        }
    }
    return 1;
}

static int flushPackets(struct StreamInfo *info,int64_t stop){
    AVPacket pkt;
    int ret;
    if (!info->out_codec_ctx)
        return 1;
    pkt.data = NULL;
    pkt.size = 0;
    av_init_packet(&pkt);
    av_log(NULL, AV_LOG_VERBOSE,"Flush packets\n");
    if((ret = avcodec_send_frame(info->out_codec_ctx, NULL))>=0){
        while (ret >=0){
            ret = avcodec_receive_packet(info->out_codec_ctx,&pkt);
            if (ret==0){
                av_log(NULL, AV_LOG_VERBOSE,"p->");
                pkt.stream_index=info->inStream->index;//compatibility
                int64_t probe =  pkt.pts==AV_NOPTS_VALUE?pkt.dts:pkt.pts;
                if (probe >= stop || (pkt.pts==AV_NOPTS_VALUE && (context.fmtFlags & AVFMT_NOTIMESTAMPS))){//observed on vc1
                 	av_log(NULL,AV_LOG_VERBOSE,"Flush pkt END: %ld\n",pkt.dts);
                 	av_packet_unref(&pkt);
                 	break;
                 }
                write_packet(info,&pkt);
            }else {
                av_packet_unref(&pkt);
                if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF)
                    av_log(NULL, AV_LOG_VERBOSE,"Flush packet-Queue empty\n");
                else 
                    av_log(NULL, AV_LOG_ERROR,"Err: Flush packet-receive error:%d\n",ret);
             }
        }
    }
    
    avcodec_free_context(&info->out_codec_ctx);
    return 1;
}
/**
 * After frames have been transcoded write remaining audio frames - if there are any
 */
static int pushTailAudio(){
    AVPacket pkt;
    struct StreamInfo *audioRef = getAudioRef();
    struct StreamInfo *videoRef = getVideoRef();
    if (!audioRef->inStream)
    	return 1;
    int64_t audioTail = av_rescale_q(context.video_trail_dts,videoRef->outStream->time_base, audioRef->outStream->time_base);

    av_init_packet(&pkt);

    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
    	struct StreamInfo *info = getStream(pkt.stream_index);
    	if (!info ){
        	av_packet_unref(&pkt);
        	continue;
    	}
        int isAudio = info->type==TYPE_AUDIO;
        if (!isAudio){
        	av_packet_unref(&pkt);
        	continue;
        }
        int64_t counter = info->outStream->cur_dts;
        counter+=av_rescale_q(pkt.duration,info->inStream->time_base,info->outStream->time_base);
        if (counter >= audioTail){
      		av_log(NULL,AV_LOG_VERBOSE,"Audio tail (P:%ld) %ld of:%ld\n", pkt.pts,counter,audioTail);
   			av_packet_unref(&pkt);
   			break;
        }
        double_t outtime= av_q2d(info->outStream->time_base)*(pkt.dts);
        double_t intime= av_q2d(info->inStream->time_base)*(pkt.dts);
        av_log(NULL,AV_LOG_VERBOSE,"**Audio Tail P/D:%ld in:%.3f out:%.3f cnt:%ld\n",pkt.dts,intime,outtime,counter);
        write_packet(info,&pkt);//unreffed there
    }
    return 1;
}

static int transcode( int64_t start, int64_t stop){
    AVPacket pkt;
    int ret;
    AVFrame *frame;
    int64_t audioTail = 0;
    struct StreamInfo *audioref = getAudioRef();
    struct StreamInfo *videoref = getVideoRef();

    if (audioref->inStream)
    		audioTail = av_rescale_q(stop,videoref->inStream->time_base,audioref->inStream->time_base);
    av_log(NULL, AV_LOG_VERBOSE,"Video stop: %ld, Audio cutoff: %ld\n",stop,audioTail);

    frame = av_frame_alloc();    
    ret = _initEncoder(videoref,frame);
    if (ret <0)
        return -1; 
    
    av_init_packet(&pkt);
        
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
    	if (pkt.dts == AV_NOPTS_VALUE){
    		av_log(NULL, AV_LOG_VERBOSE,"Skip frame-invalid DTS\n");
    		continue; //Not able
    	}
    	struct StreamInfo *info = getStream(pkt.stream_index);
    	if (!info){
            //unusable packet
            av_packet_unref(&pkt);
            continue;
    	}

    	int isVideo = info->type==TYPE_VIDEO;
        if (!isVideo){
        	if (pkt.dts <= audioTail)
        		write_packet(info,&pkt);
        	continue;
        }
            
        double_t dtime= av_q2d(info->inStream->time_base)*(pkt.dts);//Instream time...
        if ((ret = decode(info->in_codec_ctx,&pkt,frame))<0) {
            av_log(NULL, AV_LOG_VERBOSE,"Buffer pkt: isKey:%d p:%ld d:%ld [%.3f] dur:%ld\n",pkt.flags, pkt.pts,pkt.dts,dtime,pkt.duration);
        }else {
        	//either PTS or DTS ..
        	int64_t pts = frame->pts;
        	if (frame->pts == AV_NOPTS_VALUE){
        		pts = frame->best_effort_timestamp;//works -not correctly on VC1
       			frame->pts = pts;
        		av_log(NULL, AV_LOG_VERBOSE,"?");
        	}
        	if (context.isDebug){
				char ptype = av_get_picture_type_char(frame->pict_type);
				double_t fptime= av_q2d(info->inStream->time_base)*(pts);
				//DTS is always==PTS- since its decoded...
				av_log(NULL, AV_LOG_VERBOSE,"[%d]%d) decode key: %d (%d) type: %c, pts: %ld time: %.3f frm dur %ld",frame->coded_picture_number,info->in_codec_ctx->frame_number,frame->key_frame,pkt.flags,ptype,pts,fptime,frame->pkt_duration);
        	}
			//if (frame->pts != AV_NOPTS_VALUE && frame->pts < start){
            if (pts < start){
				av_log(NULL, AV_LOG_VERBOSE,"- Ignore\n");
				av_packet_unref(&pkt);
				continue;
			}else if (pts > stop){
				av_log(NULL, AV_LOG_VERBOSE,"- End of GOP: %ld\n",pts);
				break;
			}
            //try to encode
            ret = av_frame_make_writable(frame);
            if (ret<0){
                av_log(NULL, AV_LOG_ERROR,"Err: frame not writable\n");
                av_packet_unref(&pkt);
                continue;
            }
            frame->pict_type = AV_PICTURE_TYPE_NONE;                               
            ret=avcodec_send_frame(info->out_codec_ctx,frame);
            // Make sure Closed Captions will not be duplicated
            av_frame_remove_side_data(frame, AV_FRAME_DATA_A53_CC);
            if (ret== AVERROR_EOF)
                av_log(NULL, AV_LOG_VERBOSE,"-Error EOF\n");
            else if (ret==AVERROR(EINVAL))
                av_log(NULL, AV_LOG_VERBOSE,"-Error EINVAL\n");
            else if (ret==AVERROR(EAGAIN))
                av_log(NULL, AV_LOG_VERBOSE,"-Error EAGAIN\n");
            else if (ret==0){
                av_log(NULL, AV_LOG_VERBOSE,"+\n");
                AVPacket enc_pkt={ .data = NULL, .size = 0 };
                av_init_packet(&enc_pkt);
                while (avcodec_receive_packet(info->out_codec_ctx,&enc_pkt)>=0){
                    enc_pkt.stream_index=info->inStream->index;//compatibility
                    write_packet(info, &enc_pkt);//will unref package...
                }
            }    
            else
                av_log(NULL, AV_LOG_ERROR,"Err: -Frame error %d\n",ret);
        }
        
        av_packet_unref(&pkt);     
    }
    av_packet_unref(&pkt);     
    flushFrames(videoref,frame);
    flushPackets(videoref,stop);
    videoref->out_codec_ctx=NULL;
    avcodec_flush_buffers(videoref->in_codec_ctx);
    av_frame_free(&frame);
    pushTailAudio();
    return 1;
}

static int split(int64_t start, int64_t stop){
	AVPacket pkt;
	struct StreamInfo *audioStream = getAudioRef();
	struct StreamInfo *videoStream = getVideoRef();
	//struct StreamInfo *streamInfo;
	int64_t check;
	int64_t zeroVDTS=0;
	int64_t zeroADTS=0;
	short flag =0;
	int64_t cnt=0;

	while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
		int isVideo = videoStream->srcIndex==pkt.stream_index;
		int isAudio = audioStream->srcIndex==pkt.stream_index;

		if (isVideo){
			 //streamInfo = videoStream;
			 check = pkt.dts;
			 if (pkt.flags == AV_PKT_FLAG_KEY && flag==0){
				 flag=1;
			 }
		}else if (isAudio) {
			 //streamInfo = audioStream;
			 check = av_rescale_q(pkt.dts,audioStream->inStream->time_base,videoStream->inStream->time_base);
		}
		else {
			av_packet_unref(&pkt);
			continue;
		}

		if (check < start || !flag){
			av_packet_unref(&pkt);
			continue;
		}
		if (check >stop){
			av_packet_unref(&pkt);
			break;
		 }
		int64_t p1 = pkt.pts;
        int64_t d1 = pkt.dts;
        if (isVideo){
        	//d1=zeroVDTS;
        	zeroVDTS=(int64_t)(cnt*videoStream->deltaDTS);
        	cnt++;
        }else if (isAudio){
        	//d1=zeroADTS;
        	zeroADTS+=pkt.duration;
        	//p1=d1;
        }
    	pkt.dts=d1;
    	pkt.pts=p1;
	    int64_t delta = p1-d1;
	    int64_t dur = pkt.duration;
	    int64_t calcDTS = isVideo?zeroVDTS-pkt.duration:zeroADTS-pkt.duration;
	    int64_t diff = d1-calcDTS;
        char type = isVideo?'V':'A';
		av_log(NULL, AV_LOG_VERBOSE,"%c) P:%ld, D:%ld(%ld),diff:%ld delta: %ld, dur:%ld\n",type,p1,d1,calcDTS,diff,delta,dur);
       int ret = av_interleaved_write_frame(context.ofmt_ctx, &pkt);
       if (ret < 0) {
           av_log(NULL, AV_LOG_ERROR,"Err: Error muxing packet\n");
          return ret;
	   }

	}
	return 1;
}

/** decode the input stream, display its data **/
static int dumpDecodingData(){
    struct StreamInfo *streamInfo;
    struct StreamInfo *audioStream = getAudioRef();
    struct StreamInfo *videoStream = getVideoRef();
	char frm;
    AVPacket pkt;
    AVFrame *frame;
    
    pkt.data = NULL;
    pkt.size = 0;
    av_init_packet(&pkt); 
    frame = av_frame_alloc(); 
    
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {

        int isVideo = videoStream->srcIndex==pkt.stream_index;
        if (isVideo) {
            streamInfo = videoStream;
            if (pkt.flags == AV_PKT_FLAG_KEY)
                frm='I';      
            else
                frm='v';      
        }else {//Audio
            frm='*';        
            streamInfo = audioStream;
        }		
        int64_t streamOffset = streamInfo->inStream->start_time;
        double_t dtsCalcTime = av_q2d(streamInfo->outStream->time_base)*pkt.dts;
        double_t ptsCalcTime = av_q2d(streamInfo->outStream->time_base)*pkt.pts;
        double_t xxx = av_q2d(streamInfo->inStream->time_base)*(pkt.dts-streamOffset);
        
        av_log(NULL, AV_LOG_INFO,"%ld [%c] P:%ld  D:%ld Pt:%.3f Dt:%.3f Time:%.3f size:%d dur:%ld flags:%d\n",streamInfo->outStream->nb_frames,frm,pkt.pts,pkt.dts,ptsCalcTime,dtsCalcTime,xxx,pkt.size,pkt.duration,pkt.flags);

        if (isVideo && context.muxMode==MODE_DUMPFRAMES) {
            int ret;
            if ((ret = decode(streamInfo->in_codec_ctx,&pkt,frame)) == 0) {
                char ptype = av_get_picture_type_char(frame->pict_type);
                double_t fptime= av_q2d(streamInfo->outStream->time_base)*(frame->pts - streamInfo->inStream->start_time);  
                //DTS is always==PTS- since its decoded...
                av_log(NULL, AV_LOG_INFO,"%d)FRM key: %d(%d) type:%c,pts:%ld time:%.3f\n",streamInfo->in_codec_ctx->frame_number,frame->key_frame,pkt.flags,ptype,frame->pts,fptime);
            }else {
                double_t dtime= av_q2d(streamInfo->outStream->time_base)*(pkt.dts - streamInfo->inStream->start_time);  
                av_log(NULL, AV_LOG_INFO,"Buffer pkt: isKey:%d p:%ld d:%ld [%.3f]\n",pkt.flags, pkt.pts,pkt.dts,dtime);            
            }
        }

          av_packet_unref(&pkt);
    }
    av_frame_free(&frame);
    return 1;                
}
/** seek to the timeslots and cut them out **/
static int seekAndMux(double_t timeslots[],int seekCount){
	struct StreamInfo *audioStream = getAudioRef();
	struct StreamInfo *videoStream = getVideoRef();
    AVRational time_base = videoStream->inStream->time_base;
    AVRational framerate = videoStream->in_codec_ctx->framerate;
    int64_t vStreamOffset = 0;
    int64_t aStreamOffset = 0;
    double_t aStreamStartTime =0.0;
    if (audioStream->inStream){
    	aStreamOffset= audioStream->inStream->start_time;
        vStreamOffset = videoStream->inStream->start_time;
        aStreamStartTime = av_q2d(audioStream->inStream->time_base)*aStreamOffset;
    }
    int64_t startOffset = vStreamOffset - aStreamOffset;
    int64_t mainOffset = (vStreamOffset<aStreamOffset)?aStreamOffset:vStreamOffset;
    double_t streamOffsetTime = av_q2d(time_base)*startOffset;
    double_t vStreamStartTime = av_q2d(time_base)*vStreamOffset;
    double_t mainOffsetTime = av_q2d(time_base)*mainOffset;
    int64_t duration = videoStream->inStream->duration;
    int res =0;

    double_t fps = (double_t)framerate.num/framerate.den;//same as get_fps
    videoStream->deltaDTS = (videoStream->outStream->time_base.den/fps);
    int64_t audioDelta =0;
    int64_t videoDelta = av_rescale_q(videoStream->deltaDTS, videoStream->outStream->time_base,videoStream->inStream->time_base);
    if (context.fmtFlags & AVFMT_NOTIMESTAMPS)
    	audioDelta = audioStream->inStream?av_rescale_q(videoStream->deltaDTS, videoStream->outStream->time_base,audioStream->inStream->time_base):0L;
    
    CutData headBorders={0,0,0,0};
    CutData tailBorders={0,0,0,0};
    
    //Correction for seeking
    int64_t first_dts = max(seekPrimaryOffset(videoStream),0);
    int64_t zeroDTS = first_dts-vStreamOffset;
    double_t zeroTime= av_q2d(time_base)*zeroDTS;
    int audioInDen=0;
    int audioOutDen=0;
	if (audioStream->inStream){
		audioInDen = audioStream->inStream->time_base.den;
		audioOutDen = audioStream->outStream->time_base.den;
	}
    av_log(NULL, AV_LOG_INFO,"Mux video - Offset: %ld (%.3f) fps: %.3f audio -offset %ld (%.3f) delta:%ld (%.3f)\n",vStreamOffset,vStreamStartTime,fps,aStreamOffset,aStreamStartTime,startOffset,streamOffsetTime);
    av_log(NULL, AV_LOG_INFO,"First IFrame DTS found: %ld, normalized: %ld (%.3f) mainOffset: %ld (%.3f)\n",first_dts,zeroDTS,zeroTime,mainOffset,mainOffsetTime);
    av_log(NULL, AV_LOG_INFO,"Video tbi: %d tbo: %d ; Audio tbi: %d tbo: %d \n",time_base.den,videoStream->outStream->time_base.den,audioInDen,audioOutDen);
    av_log(NULL, AV_LOG_INFO,"Video IN: %s long:%s\n",context.ifmt_ctx->iformat->name,context.ifmt_ctx->iformat->long_name);
    if (context.ofmt_ctx)
        av_log(NULL, AV_LOG_INFO,"Video OUT: %s long:%s\n",context.ofmt_ctx->oformat->name,context.ofmt_ctx->oformat->long_name);

    context.streamOffset = startOffset; 
    audioStream->frame_nbr=0;
    videoStream->frame_nbr=0;

    if (context.muxMode == MODE_SPLIT){//Pure testing
        int64_t ptsStart = ptsFromTime(timeslots[0]+mainOffsetTime+zeroTime,time_base);
        int64_t ptsEnd = ptsFromTime(timeslots[1]+mainOffsetTime+zeroTime,time_base);
        res = split(ptsStart,ptsEnd);
        return res;
    }
    
    if (context.muxMode >= MODE_DUMP){
        res = dumpDecodingData();
        return res;
    }

    int64_t lookback = 5*videoDelta;
    int i;
    for (i = 0; i < (seekCount); ++i){
        double_t startSecs = timeslots[i];
        double_t endSecs = timeslots[++i];
        if (endSecs < startSecs)
            endSecs=startSecs+duration;
            
        int64_t ptsStart = ptsFromTime(startSecs+mainOffsetTime+zeroTime,time_base);
        int64_t ptsEnd = ptsFromTime(endSecs+mainOffsetTime+zeroTime,time_base);
        av_log(NULL, AV_LOG_VERBOSE,"************************\nSearch from %.3f to %.3f pts: %ld - %ld lookback: %ld\n",startSecs,endSecs,ptsStart,ptsEnd,lookback);
        seekHeadGOP(videoStream,ptsStart,&headBorders);//Header GOP
        seekTailGOP(videoStream,ptsEnd,&tailBorders); //TAIL GOP
        
        if (headBorders.start == headBorders.end || tailBorders.start==tailBorders.end){
            av_log(NULL, AV_LOG_ERROR,"Err: Seek times out of range. Aborted\n");
            return -1;
        }
        //OR: AVSEEK_FLAG_BACKWARD / AVSEEK_FLAG_ANY
         if(av_seek_frame(context.ifmt_ctx, videoStream->srcIndex, headBorders.start-lookback,AVSEEK_FLAG_BACKWARD ) < 0){
            av_log(NULL, AV_LOG_ERROR,"Err: av_seek_frame failed.\n");
            return -1;
        }
        avcodec_flush_buffers(videoStream->in_codec_ctx);

        /*
         * audio sync - when transcoding we'll have a pts-dts offset: audiosync must go back (earlier)
         * On no PTS codes like vp9 we calculate it.
         */
        if (context.muxMode == MODE_TRANSCODE){
        	int64_t audioSync=0;
        	if (audioStream->inStream){
        		if (audioDelta == 0 && headBorders.pts != AV_NOPTS_VALUE)
        			audioSync = headBorders.pts - headBorders.dts;
        		else
				audioSync = audioDelta*3;
        		context.audio_sync_dts= av_rescale_q( headBorders.dts-audioSync,videoStream->inStream->time_base, audioStream->inStream->time_base);
        		av_log(NULL, AV_LOG_VERBOSE,"Audio sync @ %ld\n",context.audio_sync_dts);
        	}
            res = transcode(headBorders.dts,tailBorders.dts);
        }
        else {
        	if (audioStream->inStream){//-1xaudio )
            	context.audio_sync_dts= av_rescale_q( headBorders.start-audioDelta,videoStream->inStream->time_base, audioStream->inStream->time_base);
            	av_log(NULL, AV_LOG_VERBOSE,"Audio sync @ %ld\n",context.audio_sync_dts);
        	}
            res = mux1(headBorders,tailBorders);
        }
        if ( res < 0){
            av_log(NULL, AV_LOG_ERROR,"Err: muxing/transcode failed\n");
            return -1;
        }
    }
    return 1;    
}

int calculateVideoLen(double_t timeslots[],int seekCount){
    double_t duration = 0.0;
    int i;
    for (i = 0; i < (seekCount); ++i){
        double_t startSecs = timeslots[i];
        double_t endSecs = timeslots[++i];
        if (endSecs > startSecs)
            duration += (endSecs - startSecs);
        
    }
    av_log(NULL, AV_LOG_INFO,"Video length is about %3.2f seconds\n",duration);
    return duration;
}

/******************** Main helper *************************/
void usage(char *arg){
        printf("usage: %s -i input [options] -s time,time,time,time..... output \n"
               "Remux a media file with libavformat and libavcodec.\n"
               "The output format is guessed according to the file extension.\n"
               "\t-s: Set the time in seconds.millis for start & stop of a chunk\n"
        	   //"\t-a: Set the audiostreams indices you'd like to use (e.g -a 1.3.5)"
        	   //"\t-v: Set the videostream you'd like to use (usually not necessary - e.g -v 2)"
        	   //"\t-l: list all streams of the container (use for the -a and -v options)"
        	   "\t-l: Sets up to 3 audio language streams to be used. (e.g -l eng,deu,fra )\n"
               "\t-r: Transcode the parts. Takes some time but is frame exact\n"
               "\t-d: debug mode\n"
               "\t-tp: decode & list all packets (no cutting)\n"
               "\t-tf: decode & list all packets & frames (no cutting)\n"
               "\n"
               "\tExample:\n"
               "\t./remux5 /home/xxx/Videos/File.m2t -s 386.080,415.760,510.460,529.320 /home/xxx/Videos/Cut.mp4\n"
               "\n"
               "\twill mux the frames between 386 - 415 and 510 - 529 seconds. So the times describe which parts you want in the target. \n"
               "\t Infos @ https://github.com/kanehekili/VideoCut \n", arg);
}

int parseArgs(int argc, char *argv[],double_t array[]) {
  int c,i, count;
  opterr = 0;
  count=0;
  char *tmp;
  while ((c = getopt (argc, argv, "l:s:drt:i:c?")) != -1){
        switch (c){
          case 's':
              i = 0;
              tmp = strtok(optarg,",");
              while (tmp != NULL) {
                array[i++]= atof(tmp);
                tmp = strtok(NULL,","); 
              }
              count=i;
              break;
          case 'd':
            av_log_set_level(AV_LOG_VERBOSE);//DEBUG IS TOO verbose
            context.isDebug=1;
            break;
          case 'r':
            context.muxMode=MODE_TRANSCODE;
            break;
          case 't':
            tmp = strtok(optarg,"");
            if (tmp[0]=='f')
                context.muxMode=MODE_DUMPFRAMES;
            else if (tmp[0]=='p')
            	context.muxMode=MODE_DUMP;
            else
                optind--;    
            break;
          case 'i':
            context.sourceFile=strtok(optarg,"");
            break;
          case 'l':
              i = 0;
        	  tmp = strtok(optarg,",");
        	  while (tmp != NULL) {
        		  if (i<LANG_COUNT)
        			  lang[i++]= tmp;
        		  tmp = strtok(NULL,",");
        	  }
        	  while (i < LANG_COUNT-1){
        		  tmp = "nix";
        		  lang[i++]=tmp;
        	  }
        	  break;
          case 'c':
        	  context.muxMode=MODE_SPLIT;
        	  break;
          case '?':
            usage(argv[0]);
            return -1;
          default:
            printf("that dont work\n");
            return -1;
         }
    }
  
    if (optind < argc){
        context.targetFile = argv[optind];
    }
    return count; 
}
static int shutDown(int ret){
    AVOutputFormat *ofmt = NULL;
    AVFormatContext *ofmt_ctx = NULL;
    ofmt_ctx = context.ofmt_ctx;
    if (ofmt_ctx == NULL) {
        return ret;
    }

    av_freep(&allStreams);
    av_freep(&context.stream_mapping);

    ofmt = ofmt_ctx->oformat;
     /* close input */
    avformat_close_input(&context.ifmt_ctx);
     /* close output */
    if (ofmt_ctx && !(ofmt->flags & AVFMT_NOFILE))
        avio_closep(&ofmt_ctx->pb);
    avformat_free_context(ofmt_ctx);
    if (ret != 0 && ret != AVERROR_EOF) {
        av_log(NULL, AV_LOG_ERROR,"Exit with error\n");
        return 1;
    }
    av_log(NULL, AV_LOG_INFO,"*Done*\n");
    return 0;
}


/****************** MAIN **************************/
int main(int argc, char **argv)
{
    double_t timeslots[255];
    int seekCount;
    int ret;

	//videoStream = malloc(sizeof(*videoStream));
    //allStreams = malloc((1+LANG_COUNT) * sizeof(*allStreams));
    allStreams = av_mallocz_array(4,sizeof(*allStreams));
    context.isDebug=0;
    context.muxMode = MODE_FAST;
    context.sourceFile = NULL;
    context.targetFile = NULL;

    
    if (argc < 3) {
        usage(argv[0]);
        return 1;
    }

    context.nprocs = get_nprocs();
    //The seeks slots...
    seekCount = parseArgs(argc,argv,timeslots);
    if (seekCount <0)
        return shutDown(EINVAL);

    if (context.sourceFile == NULL || context.targetFile == NULL){
        av_log(NULL, AV_LOG_ERROR,"Err: No file given!\n");
        return shutDown(ENOENT); 
    }

    printf("Args: %s -> %s \n",context.sourceFile,context.targetFile);

    if ((ret=_setupStreams(&context))<0)
        return shutDown(1);

    /** ENTER MUX **/
    context.videoLen = calculateVideoLen(timeslots,seekCount);
    ret=seekAndMux(timeslots,seekCount);

    if (ret)
        av_write_trailer(context.ofmt_ctx);
    return shutDown(0);
} 

